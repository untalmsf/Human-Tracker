def main(args_list=None):
    import cv2, numpy as np, csv, os, warnings, argparse, time
    import sys
    from ultralytics import YOLO
    from pyfirmata2 import Arduino
    import yt_dlp
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import re

    warnings.filterwarnings("ignore", message=".*autocast.*")

    # Parametros de la interfaz
    parser = argparse.ArgumentParser(description="Person Tracker con YOLOv8 + click-selector")
    parser.add_argument("--camera", type=int)
    parser.add_argument("--camera-sec", type=int)
    parser.add_argument("--video")
    parser.add_argument("--live", type=str, help="URL o parámetro para obtener stream en vivo")
    parser.add_argument("--youtube", type=str, help="URL de YouTube a utilizar como fuente de video")
    parser.add_argument("--earthcam", type=str, help="URL de EarthCam a utilizar como fuente de video")
    parser.add_argument("--out-base", required=True, help="Ruta base para guardar los archivos de salida")
    parser.add_argument("--no-boxes", action="store_true", help="No dibujar cuadros alrededor de las personas detectadas")
    parser.add_argument("--camera-doble", action="store_true", help="Usar cámara secundaria")
    parser.add_argument("--com", help="Puerto COM para la placa Arduino")
    parser.add_argument("--resolution", default="640x480")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--gainX", type=float, default=1.0, help="Ganancia de la cámara X")
    parser.add_argument("--gainY", type=float, default=1.0, help="Ganancia de la cámara Y")
    parser.add_argument("--zoom", type=float, default=110.0, help="Zoom de la cámara")
    parser.add_argument("--no-save", action="store_true", help="No guardar archivos")
    parser.add_argument("--vidriera-mode", action="store_true", help="Modo depuración")

    args = parser.parse_args(args_list)


    # Validación de funciones avanzadas
    res_w, res_h = map(int, args.resolution.split("x"))
    fps = args.fps

    # Variables de la base rotativa
    baseX, baseY = 80, 100
    servoPos = [baseX, baseY]
    last_det_t, timeout = time.time(), 5

    # Inicialización de la placa Arduino y servos
    if args.camera_doble:
        try:
            board = Arduino(args.com)
            time.sleep(0.5)
            servo_x = board.get_pin("d:9:s")
            servo_y = board.get_pin("d:10:s")
            servo_x.write(servoPos[0])
            servo_y.write(servoPos[1])
            time.sleep(0.5)
        except Exception as e:
            print("Error al inicializar servos:", e)

    # Generación de nombre de archivos
    def unico(base_path, ext):
        nombre = f"{base_path}.{ext}"
        i = 1
        while os.path.exists(nombre):
            nombre = f"{base_path}_{i}.{ext}"
            i += 1
        return nombre

    # Crear carpeta 'output' si no existe
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Construir ruta base de archivos dentro de 'output'
    base = os.path.join(output_dir, os.path.basename(args.out_base))

    nombre_base = os.path.splitext(os.path.basename(base))[0]
    vid_sec_base = os.path.join(output_dir, f"{nombre_base}_cam_sec")

    vid_out = unico(base, "avi") if not args.no_save else None
    vid_out_sec = unico(vid_sec_base, "avi") if args.camera_sec and not args.no_save else None

    # Extraer nombre base sin extensión para usar en el CSV
    csv_base = os.path.join(output_dir, f"seguimiento_{nombre_base}")
    csv_out = unico(csv_base, "csv") if not args.no_save else None

    # Función para obtener la URL del stream
    def get_stream_url(url):
        ydl_opts = {'quiet': True, 'skip_download': True, 'format': 'best[ext=mp4]/best'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            if 'url' in info_dict:
                return info_dict['url']
            elif 'formats' in info_dict:
                for fmt in info_dict['formats']:
                    if fmt.get('vcodec') != 'none':
                        return fmt['url']
        raise RuntimeError("No se pudo obtener la URL del stream")

    # Inicialización del video o stream
    def get_earthcam_stream(url):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(options=options)

        try:
            driver.get(url)
            html = driver.page_source
        except Exception as e:
            driver.quit()
            raise RuntimeError(f"No se pudo acceder a la página EarthCam: {e}")

        driver.quit()

        # Buscar URLs .m3u8 en el HTML
        matches = re.findall(r'https?://[^\s"\']+\.m3u8', html)
        if not matches:
            raise RuntimeError("No se encontró ninguna URL de stream (.m3u8) en la página.")
        
        return matches[0]

    cap = None
    try:
        if args.youtube:
            stream_url = get_stream_url(args.youtube)
            cap = cv2.VideoCapture(stream_url)
        elif args.earthcam:
            stream_url = get_earthcam_stream(args.earthcam)
            print(f"Conectando al stream de EarthCam: {stream_url}")
            cap = cv2.VideoCapture(stream_url)
        elif args.live:
            stream_url = get_stream_url(args.live)
            cap = cv2.VideoCapture(stream_url)
        else:
            cap = cv2.VideoCapture(args.camera if args.camera is not None else args.video)
    except Exception as e:
        print(f"Error al abrir el video/stream: {e}")
        sys.exit(1)

    if not cap or not cap.isOpened():
        print("No se pudo abrir el stream o video.")
        sys.exit(1)

    # Configuración de la captura de video
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  res_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res_h)
    cap.set(cv2.CAP_PROP_FPS,          fps)

    # Configuración de la cámara secundaria
    cap_sec = None
    if args.camera_doble and args.camera_sec is not None:
        cap_sec = cv2.VideoCapture(args.camera_sec)
        cap_sec.set(cv2.CAP_PROP_FRAME_WIDTH, res_w)
        cap_sec.set(cv2.CAP_PROP_FRAME_HEIGHT, res_h)
        cap_sec.set(cv2.CAP_PROP_FPS, fps)

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(vid_out, fourcc, fps, (res_w, res_h)) if vid_out else None
    out_sec = cv2.VideoWriter(vid_out_sec, fourcc, fps, (res_w, res_h)) if vid_out_sec and args.camera_sec else None

    model = YOLO("yolov10s.pt")
    seguido_id, next_id = None, 0
    cands, log = {}, []
    UMBRAL = 50
    etiquetas = ["Izquierda", "Centro-Izq", "Centro-Der", "Derecha"]

    # Función para seleccion de persona con click
    def click(event, x, y, flags, param):
        nonlocal seguido_id, cands
        if event == cv2.EVENT_LBUTTONDOWN:
            for i, (centro, x1, y1, w, h) in cands.items():
                if x1 < x < x1 + w and y1 < y < y1 + h:
                    seguido_id = i
                    break

    cv2.namedWindow("Seguimiento de persona")
    cv2.setMouseCallback("Seguimiento de persona", click)

    # Función para detectar personas
    def detect(frame):
        r = model.predict(frame, imgsz=640, conf=0.6, verbose=False)[0]
        outs=[]
        for b in r.boxes:
            if int(b.cls[0])==0 and float(b.conf[0])>0.6:
                x1,y1,x2,y2=b.xyxy[0].tolist(); w,h=x2-x1,y2-y1
                outs.append(((int(x1+w/2),int(y1+h/2)), int(x1),int(y1),int(w),int(h)))
        return outs

    # Función para asociar detecciones con IDs
    def associate(nuevos):
        nonlocal next_id, cands
        vis=[]
        for c,x,y,w,h in nuevos:
            best, dmin = None, 1e9
            for i, (c_old, *_) in cands.items():
                d = np.hypot(c[0] - c_old[0], c[1] - c_old[1])
                if d < dmin and d < UMBRAL:
                    best, dmin = i, d
            if best is not None:
                cands[best] = (c, x, y, w, h)
                vis.append((best, c, x, y, w, h))
            else:
                cands[next_id] = (c, x, y, w, h)
                vis.append((next_id, c, x, y, w, h))
                next_id += 1
        return vis

    # Función para mover los servos de la base rotativa
    def move_servos(cx,cy):
        global servoPos
        # Campo de visión estimado de la cámara
        fov_x = 110  # grados horizontal
        fov_y = 60   # grados vertical aproximado

        # Diferencia en píxeles desde el centro de la imagen
        dx = cx - (res_w // 2)
        dy = cy - (res_h // 2)

        # Convertir la diferencia de píxeles a ángulo
        angle_x = ((dx / res_w) * fov_x) + args.gainX
        angle_y = ((dy / res_h) * fov_y) * args.gainY

        # Calcular nuevos ángulos absolutos a partir del centro (base)
        new_x = np.clip(baseX - angle_x, 0, 180)
        new_y = np.clip(baseY - angle_y, 75, 120)  # eje invertido para Y

        servoPos = [new_x, new_y]
        servo_x.write(new_x)
        servo_y.write(new_y)

    def zoom(frame, zoom_pct):
        if zoom_pct <= 100:
            return frame  # sin zoom o reducción no aplicada

        zoom_factor = zoom_pct / 100.0
        h, w = frame.shape[:2]

        # Calculamos el tamaño de recorte
        new_w = int(w / zoom_factor)
        new_h = int(h / zoom_factor)

        # Coordenadas para recorte centrado
        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2
        x2 = x1 + new_w
        y2 = y1 + new_h

        cropped = frame[y1:y2, x1:x2]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


    # Bucle principal de captura y procesamiento
    while True:
        if cv2.getWindowProperty("Seguimiento de persona", cv2.WND_PROP_VISIBLE) < 1:
            break
        ret, frame = cap.read()
        if not ret: break
        if frame.shape[1]!=res_w or frame.shape[0]!=res_h:
            frame=cv2.resize(frame,(res_w,res_h))
        vis = associate(detect(frame))
        if seguido_id is None and vis: seguido_id=vis[0][0]
        
        if args.vidriera_mode:
            zona_w = res_w // 4
            for i in range(1, 4):
                cv2.line(frame, (i * zona_w, 0), (i * zona_w, res_h), (200, 200, 200), 2)

        for idv, (cx, cy), x, y, w, h in vis:
            color = (0, 255, 0) if idv == seguido_id else (255, 0, 0)
            if not args.no_boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, f"ID:{idv}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            if idv == seguido_id:
                last_det_t = time.time()
                if args.vidriera_mode:
                    zona = etiquetas[min(cx // (res_w // 4), 3)]
                else:
                    zona = "General"
                log.append((int(cap.get(cv2.CAP_PROP_POS_FRAMES)), idv, zona))
                if args.camera_doble:
                    move_servos(cx, cy)


        if args.camera_doble and time.time()-last_det_t>timeout:
            servo_x.write(baseX)
            servo_y.write(baseY)
            servoPos=[baseX,baseY]
        if out: out.write(frame)

        # Procesamiento de la cámara secundaria
        if cap_sec:
            ret2, frame2 = cap_sec.read()
            if ret2:
                frame2 = zoom(frame2, args.zoom)
                # Concatenar las dos cámaras verticalmente (tipo Nintendo DS)
                frame_combined = np.vstack((frame, frame2))
                if out_sec: out_sec.write(frame2)
            else:
                frame_combined = frame  # fallback si falla cap_sec
            cv2.imshow("Seguimiento de persona", frame_combined)
        else:
            cv2.imshow("Seguimiento de persona", frame)

        if cv2.waitKey(1)&0xFF==27: break

    # Finalización y limpieza
    cap.release()
    cv2.destroyAllWindows()
    if out: out.release()
    if out_sec: out_sec.release()
    if csv_out:
        with open(csv_out,"w",newline="") as f:
            csv.writer(f).writerows([("frame","id","zona"),*log])
    if cap_sec:  cap_sec.release()
    if args.camera_doble: board.exit()
    print("Finalizado.")
    
if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
