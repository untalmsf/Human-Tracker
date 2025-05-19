import cv2
import numpy as np
import csv
import os
import warnings
import argparse
from ultralytics import YOLO
from pyfirmata2 import Arduino
import time

warnings.filterwarnings("ignore", message=".*autocast.*")

# ────────────────────── ARGUMENTOS CLI ──────────────────────
parser = argparse.ArgumentParser(description="Person Tracker con YOLOv8")
parser.add_argument("--camera", type=int, help="Índice de cámara a usar")
parser.add_argument("--video", help="Archivo de video a procesar")
parser.add_argument("--out-base", required=True, help="Base de nombre para archivos de salida")
parser.add_argument("--no-boxes", action="store_true", help="Desactivar dibujo de bounding boxes")
parser.add_argument("--modo-rotativa", action="store_true")
parser.add_argument("--com", type=str)
parser.add_argument("--resolution", type=str, default="640x480", help="Resolución WIDTHxHEIGHT")
parser.add_argument("--fps", type=float, default=30.0, help="FPS deseados para la salida")
args = parser.parse_args()

# ────────────────── CONFIGURACIÓN GENERAL ──────────────────
res_width, res_height = map(int, args.resolution.split("x"))
fps = args.fps

# Servos (sólo si usas la base rotativa)
baseX, baseY = 80, 100
servoPos = [baseX, baseY]
last_detection_time = time.time()
timeout = 5  # segundos sin detección → servos a home

if args.modo_rotativa:
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

# ─────────────────── NOMBRES DE ARCHIVO ────────────────────
def nombre_unico(base, ext):
    i = 1
    nombre = f"{base}.{ext}"
    while os.path.exists(nombre):
        nombre = f"{base}_{i}.{ext}"
        i += 1
    return nombre

video_filename = nombre_unico(args.out_base, "avi")
csv_filename   = nombre_unico("seguimiento", "csv")

# ───────────────────── CAPTURA DE VIDEO ─────────────────────
if args.camera is not None:
    cap = cv2.VideoCapture(args.camera)
    # Forzar resolución y FPS en la cámara
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  res_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res_height)
    cap.set(cv2.CAP_PROP_FPS,          fps)
else:
    cap = cv2.VideoCapture(args.video)

# ───────────────────── VIDEO WRITER ────────────────────────
fourcc = cv2.VideoWriter_fourcc(*"XVID")
out    = cv2.VideoWriter(video_filename, fourcc, fps, (res_width, res_height))

# ───────────────────── MODELO YOLOv8 ───────────────────────
model = YOLO("yolov8m.pt")

# ─────────────── VARIABLES DE SEGUIMIENTO ──────────────────
seguido_id = None
siguiente_id = 0
candidatos = {}
pos_iniciales = {}
seguimiento_log = []

umbral_dist = 50  # pixeles

# ───────────────── FUNCIONES AUXILIARES ────────────────────
def procesar_detecciones(img):
    results = model.predict(img, imgsz=640, conf=0.6, verbose=False)[0]
    outs = []
    for box in results.boxes:
        if int(box.cls[0]) == 0 and float(box.conf[0]) > 0.6:  # persona
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            w, h = x2 - x1, y2 - y1
            cx, cy = int(x1 + w / 2), int(y1 + h / 2)
            outs.append(((cx, cy), int(x1), int(y1), int(w), int(h)))
    return outs

def asociar(nuevos, umbral):
    global siguiente_id
    visibles = []
    for centro, x, y, w, h in nuevos:
        mejor_id, dist_min = None, float("inf")
        for idc, (cent_ant, *_) in candidatos.items():
            dist = np.hypot(centro[0]-cent_ant[0], centro[1]-cent_ant[1])
            if dist < dist_min and dist < umbral:
                dist_min, mejor_id = dist, idc
        if mejor_id is not None:
            candidatos[mejor_id] = (centro, x, y, w, h)
            visibles.append((mejor_id, centro, x, y, w, h))
        else:
            candidatos[siguiente_id] = (centro, x, y, w, h)
            visibles.append((siguiente_id, centro, x, y, w, h))
            siguiente_id += 1
    return visibles

def actualizar_servos(cx, cy):
    global servoPos
    frame_cx, frame_cy = res_width//2, res_height//2
    err_x = frame_cx - cx
    err_y = cy - frame_cy
    Kp_x, Kp_y = 0.05, 0.03
    servoPos[0] = np.clip(servoPos[0] + Kp_x*err_x, 0, 180)
    servoPos[1] = np.clip(servoPos[1] + Kp_y*err_y, 75, 120)
    servo_x.write(servoPos[0])
    servo_y.write(servoPos[1])

# ─────────────────────── BUCLE MAIN ────────────────────────
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Si la fuente no coincide con la resolución deseada, re-escalar.
    if frame.shape[1] != res_width or frame.shape[0] != res_height:
        frame = cv2.resize(frame, (res_width, res_height))

    nuevos = procesar_detecciones(frame)
    visibles = asociar(nuevos, umbral_dist)

    if seguido_id is None and visibles:
        seguido_id = visibles[0][0]

    zona_w = res_width // 4
    etiquetas = ["Izquierda", "Centro-Izq", "Centro-Der", "Derecha"]

    # Dibujar zonas
    for i in range(1, 4):
        cv2.line(frame, (i*zona_w, 0), (i*zona_w, res_height), (200,200,200), 2)

    # Bounding boxes
    if not args.no_boxes:
        for idv, centro, x, y, w, h in visibles:
            color = (0,255,0) if idv == seguido_id else (255,0,0)
            cv2.rectangle(frame, (x,y), (x+w,y+h), color, 2)
            cv2.putText(frame, f"ID:{idv}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Log y servos
    for idv, (cx,cy), *_ in visibles:
        if idv == seguido_id:
            last_detection_time = time.time()
            zona = etiquetas[min(cx//zona_w,3)]
            frame_num = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            seguimiento_log.append((frame_num, idv, zona))
            if args.modo_rotativa:
                actualizar_servos(cx, cy)
            break

    # Timeout servos
    if args.modo_rotativa and time.time()-last_detection_time > timeout:
        servo_x.write(baseX); servo_y.write(baseY)
        servoPos[:] = [baseX, baseY]

    out.write(frame)
    cv2.imshow("Seguimiento de persona", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

# ───────────────────── FIN & LIMPIEZA ─────────────────────
if args.modo_rotativa:
    board.exit()
cap.release()
out.release()
cv2.destroyAllWindows()

# Guardar CSV
with open(csv_filename, "w", newline="") as f:
    csv.writer(f).writerows([("frame","id","zona"), *seguimiento_log])

print(f"Video guardado en: {video_filename}")
print(f"Log guardado en  : {csv_filename}")
