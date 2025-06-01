import cv2, numpy as np, csv, os, warnings, argparse, time
import sys
from ultralytics import YOLO
from pyfirmata2 import Arduino
import yt_dlp

warnings.filterwarnings("ignore", message=".*autocast.*")

# Parametros de la interfaz
parser = argparse.ArgumentParser(description="Person Tracker con YOLOv8 + click-selector")
parser.add_argument("--camera", type=int)
parser.add_argument("--video")
parser.add_argument("--live", type=str, help="URL o parámetro para obtener stream en vivo")
parser.add_argument("--youtube", type=str, help="URL de YouTube a utilizar como fuente de video")
parser.add_argument("--earthcam", type=str, help="URL de EarthCam a utilizar como fuente de video")
parser.add_argument("--out-base", required=True)
parser.add_argument("--no-boxes", action="store_true")
parser.add_argument("--camera-doble", action="store_true")
parser.add_argument("--com")
parser.add_argument("--resolution", default="640x480")
parser.add_argument("--fps", type=float, default=30.0)
parser.add_argument("--no-save", action="store_true", help="No guardar archivos")
args = parser.parse_args()

# Variables de la base rotativa
res_w, res_h = map(int, args.resolution.split("x"))
fps = args.fps
baseX, baseY = 80, 100
servoPos = [baseX, baseY]
last_det_t, timeout = time.time(), 5

# Inicialización de la placa Arduino y servos
if args.camera_doble:
    board = Arduino(args.com); time.sleep(.5)
    servo_x = board.get_pin("d:9:s")
    servo_y = board.get_pin("d:10:s")
    servo_x.write(baseX); servo_y.write(baseY); time.sleep(.5)

# Generación de nombre de archivos
def unico(base_path, ext):
    nombre = f"{base_path}.{ext}"
    i = 1
    while os.path.exists(nombre):
        nombre = f"{base_path}_{i}.{ext}"
        i += 1
    return nombre

output_dir = os.path.dirname(args.out_base)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

base = args.out_base
vid_out = unico(base, "avi") if not args.no_save else None
csv_out = unico(base, "csv") if not args.no_save else None

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
cap = None
try:
    if args.youtube:
        stream_url = get_stream_url(args.youtube)
        cap = cv2.VideoCapture(stream_url)
    elif args.earthcam:
        stream_url = get_stream_url(args.earthcam)
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

fourcc = cv2.VideoWriter_fourcc(*"XVID")
out = cv2.VideoWriter(vid_out, fourcc, fps, (res_w, res_h)) if vid_out else None

model = YOLO("yolov8m.pt")
seguido_id, next_id = None, 0
cands, log = {}, []
UMBRAL = 50
etiquetas = ["Izquierda", "Centro-Izq", "Centro-Der", "Derecha"]

# Función para seleccion de persona con click
def click(event, x, y, flags, param):
    global seguido_id
    if event == cv2.EVENT_LBUTTONDOWN:
        for i, (centro, x1, y1, w, h) in cands.items():
            if x1 < x < x1+w and y1 < y < y1+h:
                seguido_id = i; break

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
    global next_id
    vis=[]
    for c,x,y,w,h in nuevos:
        best, dmin=None,1e9
        for i,(c_old,*_) in cands.items():
            d=np.hypot(c[0]-c_old[0], c[1]-c_old[1])
            if d<dmin and d<UMBRAL: best,dmin=i,d
        if best is not None:
            cands[best]=(c,x,y,w,h); vis.append((best,c,x,y,w,h))
        else:
            cands[next_id]=(c,x,y,w,h); vis.append((next_id,c,x,y,w,h)); next_id+=1
    return vis

# Función para mover los servos de la base rotativa
def move_servos(cx,cy):
    global servoPos
    errx, erry = (res_w//2-cx), (cy-res_h//2)
    servoPos[0]=np.clip(servoPos[0]+0.05*errx, 0,180)
    servoPos[1]=np.clip(servoPos[1]+0.03*erry, 75,120)
    servo_x.write(servoPos[0]); servo_y.write(servoPos[1])

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
    zona_w = res_w//4
    for i in range(1,4): cv2.line(frame,(i*zona_w,0),(i*zona_w,res_h),(200,200,200),2)
    for idv,(cx,cy),x,y,w,h in vis:
        color=(0,255,0) if idv==seguido_id else (255,0,0)
        if not args.no_boxes:
            cv2.rectangle(frame,(x,y),(x+w,y+h),color,2)
            cv2.putText(frame,f"ID:{idv}",(x,y-10),cv2.FONT_HERSHEY_SIMPLEX,0.5,color,2)
        if idv==seguido_id:
            last_det_t=time.time()
            zona=etiquetas[min(cx//zona_w,3)]
            log.append((int(cap.get(cv2.CAP_PROP_POS_FRAMES)), idv, zona))
            if args.camera_doble: move_servos(cx,cy)
    if args.camera_doble and time.time()-last_det_t>timeout:
        servo_x.write(baseX); servo_y.write(baseY); servoPos=[baseX,baseY]
    if out: out.write(frame)
    cv2.imshow("Seguimiento de persona", frame)
    if cv2.waitKey(1)&0xFF==27: break

# Finalización y limpieza
if args.camera_doble: board.exit()
cap.release(); cv2.destroyAllWindows()
if out: out.release()
if csv_out:
    with open(csv_out,"w",newline="") as f:
        csv.writer(f).writerows([("frame","id","zona"),*log])
print("Finalizado.")
