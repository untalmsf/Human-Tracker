class HumanTracker:
    def __init__(self, args):
        import time
        from ultralytics import YOLO
        import warnings

        self.args = args

        # Resolución y FPS
        self.res_w, self.res_h = map(int, args.resolution.split("x"))
        self.fps = args.fps

        # Base rotativa
        self.baseX, self.baseY = 80, 100
        self.servoPos = [self.baseX, self.baseY]
        self.last_det_t = time.time()
        self.timeout = 5

        # Arduino / servos
        self.board = None
        self.servo_x = None
        self.servo_y = None

        # Modelo YOLO
        warnings.filterwarnings("ignore", message=".*autocast.*")
        self.model = YOLO("yolov10n.pt")

        # Seguimiento
        self.cands = {}
        self.next_id = 0
        self.UMBRAL = 50
        self.id_actual = None
        self.persona_actual = None
        self.frames_perdido = 0
        self.log = []

        # Capturas y salidas
        self.cap = None
        self.cap_sec = None
        self.out = None
        self.out_sec = None
        self.csv_out = None

        # Tkinter / GUI
        self.root = None
        self.canvas = None
        self.canvas_sec = None

        # Imagenes
        self.frame = None
        self.frame2 = None

        # Constantes
        self.etiquetas = ["Izquierda", "Centro-Izq", "Centro-Der", "Derecha"]
        self.opacidad_secundaria = 0.5 # Opacidad de la cámara secundaria

        # Rutas de salida
        self.output_dir = "output"
        self.base = None
        self.vid_out = None
        self.vid_out_sec = None
        self.csv_base = None
        self.nombre_base = None

    def run(self):
        import os
        import cv2
        import time
        import csv
        from PIL import Image, ImageTk
        import tkinter as tk


        # Crear carpeta 'output' si no existe
        os.makedirs(self.output_dir, exist_ok=True)

        # Construir ruta base de archivos dentro de 'output'
        self.base = os.path.join(self.output_dir, os.path.basename(self.args.out_base))

        self.nombre_base = os.path.splitext(os.path.basename(self.base))[0]
        vid_sec_base = os.path.join(self.output_dir, f"{self.nombre_base}_cam_sec")

        self.vid_out = self.unico(self.base, "avi") if not self.args.no_save else None
        self.vid_out_sec = self.unico(vid_sec_base, "avi") if self.args.camera_sec and not self.args.no_save else None

        # Extraer nombre base sin extensión para usar en el CSV
        self.csv_base = os.path.join(self.output_dir, f"seguimiento_{self.nombre_base}")
        self.csv_out = self.unico(self.csv_base, "csv") if not self.args.no_save else None

        # Inicialización de la placa Arduino y servos
        if self.args.camera_doble:
            try:
                from pyfirmata2 import Arduino
                self.board = Arduino(self.args.com)
                time.sleep(0.5)
                self.servo_x = self.board.get_pin("d:9:s")
                self.servo_y = self.board.get_pin("d:10:s")
                self.servo_x.write(self.servoPos[0])
                self.servo_y.write(self.servoPos[1])
                time.sleep(0.5)
            except Exception as e:
                print("Error al inicializar servos:", e)
                raise RuntimeError(f"No se pudo inicializar la placa Arduino en {self.args.com}. Asegúrate de que el puerto es correcto y la placa está conectada.") from e

        # Abrir fuente de video
        self.cap = self.abrir_fuente_principal()
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir el stream o video. Asegúrate de que la fuente es válida y accesible.") from None
            
        
        # Configuración de la captura de video
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.res_w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.res_h)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        # Cámara secundaria
        if self.args.camera_doble and self.args.camera_sec is not None:
            self.cap_sec = cv2.VideoCapture(self.args.camera_sec)
            self.cap_sec.set(cv2.CAP_PROP_FRAME_WIDTH, self.res_w)
            self.cap_sec.set(cv2.CAP_PROP_FRAME_HEIGHT, self.res_h)
            self.cap_sec.set(cv2.CAP_PROP_FPS, self.fps)

        # Escritores
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        if self.vid_out:
            self.out = cv2.VideoWriter(self.vid_out, fourcc, self.fps, (self.res_w, self.res_h))
        if self.vid_out_sec:
            self.out_sec = cv2.VideoWriter(self.vid_out_sec, fourcc, self.fps, (self.res_w, self.res_h))

        # Tkinter GUI
        self.root = tk.Toplevel()
        self.root.title("Seguimiento de persona")

        # Mantener ventana al frente
        self.root.lift()
        self.root.attributes('-topmost', True) 
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))

        # Maximizar ventana en Windows
        self.root.state("zoomed") 
        self.root.configure(bg="black")

        # Canvas principal (cámara principal)
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.click_tkinter)

        if self.args.camera_doble and self.args.camera_sec is not None:
            # Canvas secundario (cámara secundaria)
            self.canvas_sec = tk.Canvas(self.root, width=640, height=480, bg="black", highlightthickness=2)
            self.canvas_sec.place(relx=1.0, rely=1.0, anchor="se") # esquina inferior derecha

        self.actualizar_frame()
        self.root.mainloop()

        # Limpieza
        self.cap.release()
        if self.out:
            self.out.release()
        if self.out_sec:
            self.out_sec.release()
        if self.csv_out:
            with open(self.csv_out, "w", newline="") as f:
                csv.writer(f).writerows([("frame", "id", "zona"), *self.log])
        if self.cap_sec:
            self.cap_sec.release()
        if self.args.camera_doble and self.board:
            self.board.exit()
        cv2.destroyAllWindows()
        print("Finalizado.")

    # Generación de nombre de archivos
    def unico(self, base_path, ext):
        import os
        nombre = f"{base_path}.{ext}"
        i = 1
        while os.path.exists(nombre):
            nombre = f"{base_path}_{i}.{ext}"
            i += 1
        return nombre
    
    # Función para obtener la URL del stream
    def get_stream_url(self, url):
        import yt_dlp
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
    def get_earthcam_stream(self, url):
        import re
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

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
        try:
            driver.get(url)
            html = driver.page_source
        except Exception as e:
            driver.quit()
            raise RuntimeError(f"No se pudo acceder a la página EarthCam: {e}")

        driver.quit()
        driver.quit()

        matches = re.findall(r'https?://[^\s"\']+\.m3u8', html)
        if not matches:
            raise RuntimeError("No se encontró ninguna URL de stream (.m3u8) en la página.")
        
        return matches[0]
    
    def abrir_fuente_principal(self):
        import cv2

        try:
            if self.args.youtube:
                stream_url = self.get_stream_url(self.args.youtube)
                return cv2.VideoCapture(stream_url)
            elif self.args.earthcam:
                stream_url = self.get_earthcam_stream(self.args.earthcam)
                print(f"Conectando al stream de EarthCam: {stream_url}")
                return cv2.VideoCapture(stream_url)
            elif self.args.live:
                stream_url = self.get_stream_url(self.args.live)
                return cv2.VideoCapture(stream_url)
            else:
                return cv2.VideoCapture(self.args.camera if self.args.camera is not None else self.args.video)
        except Exception as e:
            print(f"Error al abrir el video/stream: {e}")
            return None
    
    # Función para seleccion de persona con click
    def click_tkinter(self, event):
        canvas_x, canvas_y = event.x, event.y
        for i, (centro, x1, y1, w, h) in self.cands.items():
            if x1 <= canvas_x <= x1 + w and y1 <= canvas_y <= y1 + h:
                self.id_actual = i
                print(f"Persona seleccionada: ID {self.id_actual}")
                break
    
    # Función para detectar personas
    def detect(self, frame):
        confianza = 0.4
        r = self.model.predict(frame, imgsz=640, conf=confianza, verbose=False)[0]
        outs = []
        for b in r.boxes:
            if int(b.cls[0]) == 0 and float(b.conf[0]) > confianza:
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                w, h = x2 - x1, y2 - y1
                outs.append(((int(x1 + w / 2), int(y1 + h / 2)), int(x1), int(y1), int(w), int(h)))
        return outs

    # Función para asociar detecciones con IDs
    def associate(self, nuevos):
        import numpy as np
        vis = []
        usados = set()  # IDs ya asignados

        for c, x, y, w, h in nuevos:
            best, dmin = None, 1e9
            for i, (c_old, *_rest) in self.cands.items():
                if i in usados:
                    continue  # ya asignado
                d = np.hypot(c[0] - c_old[0], c[1] - c_old[1])
                if d < dmin and d < self.UMBRAL:
                    best, dmin = i, d
            if best is not None:
                self.cands[best] = (c, x, y, w, h)
                usados.add(best)
                vis.append((best, c, x, y, w, h))
            else:
                self.cands[self.next_id] = (c, x, y, w, h)
                vis.append((self.next_id, c, x, y, w, h))
                usados.add(self.next_id)
                self.next_id += 1

        return vis

    
    # Función para mover los servos de la base rotativa
    def move_servos(self, cx, cy):
        import numpy as np

        # Campo de visión estimado
        fov_x = 110 # grados horizontal
        fov_y = 60  # grados vertical

        # Diferencia en píxeles desde el centro de la imagen
        dx = cx - (self.res_w // 2)
        dy = cy - (self.res_h // 2)

        # Convertir la diferencia de píxeles a ángulo
        angle_x = ((dx / self.res_w) * fov_x) + self.args.gainX
        angle_y = ((dy / self.res_h) * fov_y) * self.args.gainY

        # Calcular nuevos ángulos absolutos a partir del centro (base)
        new_x = np.clip(self.baseX - angle_x, 0, 180)
        new_y = np.clip(self.baseY - angle_y, 75, 120) # eje invertido para Y

        self.servoPos = [new_x, new_y]
        self.servo_x.write(new_x)
        self.servo_y.write(new_y)

    def zoom(self, frame, zoom_pct):
        import cv2
        if zoom_pct <= 100:
            return frame  # sin zoom o reducción

        zoom_factor = zoom_pct / 100.0
        h, w = frame.shape[:2]
        zoom_factor = zoom_pct / 100.0
        h, w = frame.shape[:2]

        # Tamaño del recorte
        new_w = int(w / zoom_factor)
        new_h = int(h / zoom_factor)

        # Coordenadas centradas
        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2
        x2 = x1 + new_w
        y2 = y1 + new_h

        cropped = frame[y1:y2, x1:x2]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        cropped = frame[y1:y2, x1:x2]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


    def actualizar_frame(self):
        import cv2
        from PIL import Image, ImageTk
        import time

        ret, self.frame = self.cap.read()
        if not ret:
            self.root.after(10, self.actualizar_frame)
            return

        if self.frame.shape[1] != self.res_w or self.frame.shape[0] != self.res_h:
            self.frame = cv2.resize(self.frame, (self.res_w, self.res_h))

        vis = self.associate(self.detect(self.frame))

        # Seguimiento
        personas_detectadas = [{"id": idv, "centro": (cx, cy)} for idv, (cx, cy), *_ in vis]

        if self.id_actual is not None:
            ids_detectados = [p['id'] for p in personas_detectadas]
            if self.id_actual in ids_detectados:
                # Se mantiene la persona actual
                self.frames_perdido = 0
                self.persona_actual = next(p for p in personas_detectadas if p['id'] == self.id_actual)
            else:
                # Persona actual no detectada
                self.frames_perdido += 1
                if self.frames_perdido >= 2 and personas_detectadas:
                    # Buscar la persona más cercana al centro de la imagen
                    # Solo si se ha perdido la persona actual por más de 2 frames
                    centro_x = self.frame.shape[1] // 2
                    self.persona_actual = min(personas_detectadas, key=lambda p: abs(p['centro'][0] - centro_x))
                    self.id_actual = self.persona_actual['id']
                    self.frames_perdido = 0
                else:
                    # Si no se ha perdido por más de 2 frames, mantener la persona actual
                    self.persona_actual = None
        else:
            # No hay persona actual, seleccionar la más cercana al centro
            if personas_detectadas:
                # Si no hay persona actual, seleccionar la más cercana al centro
                centro_x = self.frame.shape[1] // 2
                self.persona_actual = min(personas_detectadas, key=lambda p: abs(p['centro'][0] - centro_x))
                self.id_actual = self.persona_actual['id']
                self.frames_perdido = 0
            else:
                # No hay personas detectadas
                self.persona_actual = None

        for idv, (cx, cy), x, y, w, h in vis:
            color = (0, 255, 0) if self.persona_actual and idv == self.persona_actual['id'] else (255, 0, 0)
            if not self.args.no_boxes:
                cv2.rectangle(self.frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(self.frame, f"ID:{idv}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        if self.persona_actual:
            self.last_det_t = time.time()
            cx, cy = self.persona_actual['centro']
            zona = "General" if not self.args.vidriera_mode else self.etiquetas[min(cx // (self.res_w // 4), 3)]
            self.log.append((int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)), self.persona_actual['id'], zona))
            if self.args.camera_doble:
                self.move_servos(cx, cy)

        if self.args.camera_doble and time.time() - self.last_det_t > self.timeout:
            self.servo_x.write(self.baseX)
            self.servo_y.write(self.baseY)
            self.servoPos = [self.baseX, self.baseY]

        if self.out:
            self.out.write(self.frame)

        frame_rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(frame_rgb)

        img_tk = ImageTk.PhotoImage(img_pil)
        self.canvas.img_tk = img_tk
        self.canvas.create_image(0, 0, anchor="nw", image=img_tk)

        if self.args.camera_doble and self.cap_sec:
            ret2, self.frame2 = self.cap_sec.read()
            if ret2:
                frame_zoom = self.zoom(self.frame2, self.args.zoom)
                if self.out_sec:
                    self.out_sec.write(frame_zoom)
                frame2_rgb = cv2.cvtColor(frame_zoom, cv2.COLOR_BGR2RGB)
                img2_pil = Image.fromarray(frame2_rgb).resize((640, 480))
                img2_tk = ImageTk.PhotoImage(img2_pil)
                self.canvas_sec.img_tk = img2_tk
                self.canvas_sec.create_image(0, 0, anchor="nw", image=img2_tk)

        self.root.after(1, self.actualizar_frame)

def main(args_list=None):
    import argparse

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

    # Instanciar y ejecutar
    app = HumanTracker(args)
    app.run()

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
