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

# --- PARSER DE ARGUMENTOS ---
parser = argparse.ArgumentParser(description="Person Tracker con YOLOv8")
parser.add_argument("--camera", type=int, help="Índice de cámara a usar")
parser.add_argument("--video", help="Archivo de video a procesar")
parser.add_argument("--out-base", required=True, help="Base de nombre para archivos de salida")
parser.add_argument("--no-boxes", action="store_true", help="Desactivar dibujo de bounding boxes")
parser.add_argument("--modo-rotativa", action="store_true")
parser.add_argument("--com", type=str)
args = parser.parse_args()
baseX = 80
baseY = 100
servoPos = [baseX, baseY]
last_detection_time = time.time()
timeout = 5  # segundos

if args.modo_rotativa:
    try:
        board = Arduino(args.com)
        time.sleep(0.5)
        servo_x = board.get_pin('d:9:s')
        servo_y = board.get_pin('d:10:s')
        servo_x.write(servoPos[0])
        servo_y.write(servoPos[1])
        time.sleep(0.5)

    except Exception as e:
        print("Error al mover servos a 90° al iniciar:", e)

# --- GENERAR NOMBRE ÚNICO ---
def generar_nombre_unico(base, extension):
    i = 1
    nombre = f"{base}.{extension}"
    while os.path.exists(nombre):
        nombre = f"{base}_{i}.{extension}"
        i += 1
    return nombre

video_filename = generar_nombre_unico(args.out_base, "avi")
csv_filename   = generar_nombre_unico("seguimiento", "csv")

# --- INICIALIZAR CAPTURA ---
if args.camera is not None:
    cap = cv2.VideoCapture(args.camera)
else:
    cap = cv2.VideoCapture(args.video)

# --- VIDEO WRITER ---
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out    = cv2.VideoWriter(video_filename, fourcc, fps, (width, height))

# --- CARGAR MODELO YOLOv8 ---
model = YOLO("yolov8m.pt")

# --- VARIABLES GLOBALES DE SEGUIMIENTO ---
seguido_id = None
siguiente_id = 0
candidatos = {}
posiciones_iniciales = {}
posiciones_finales   = {}
seguimiento_log = []

# --- PARÁMETROS DE SEGUIMIENTO ---
umbral_distancia    = 50
max_frames_perdido  = 30

# --- CALLBACK DE MOUSE ---
def click(event, x, y, flags, param):
    global seguido_id
    if event == cv2.EVENT_LBUTTONDOWN:
        for idv, (_centro, x1, y1, w, h) in candidatos.items():
            if x1 < x < x1 + w and y1 < y1 + h:
                seguido_id = idv
                break

cv2.namedWindow("Seguimiento de persona")
cv2.setMouseCallback("Seguimiento de persona", click)

# --- FUNCIONES AUXILIARES ---
def procesar_detecciones(imagen):
    results = model.predict(imagen, imgsz=640, conf=0.6, verbose=False)[0]
    output = []
    for box in results.boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        if cls == 0 and conf > 0.6:  # clase 0 = persona
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            w, h = x2 - x1, y2 - y1
            cx, cy = int(x1 + w / 2), int(y1 + h / 2)
            output.append(((cx, cy), int(x1), int(y1), int(w), int(h)))
    return output

def asociar_detecciones(nuevos, umbral):
    global siguiente_id
    visibles = []
    usados = set()
    for centro, x, y, w, h in nuevos:
        mejor_id, mejor_dist = None, float('inf')
        for idc, (cent_ant, *_) in candidatos.items():
            dist = np.hypot(centro[0] - cent_ant[0], centro[1] - cent_ant[1])
            if dist < mejor_dist and dist < umbral:
                mejor_dist, mejor_id = dist, idc
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
    frame_width, frame_height = 640, 480
    center_x, center_y = frame_width // 2, frame_height // 2

    # Error entre el centro del frame y el centro de la persona
    error_x = center_x - cx  # Invertido: si está a la derecha, girar a la derecha
    error_y = cy - center_y  # Si está abajo, mirar abajo

    # Ganancia proporcional
    Kp_x = 0.05  # Aumentá si querés giros más rápidos
    Kp_y = 0.03

    # Calcular cuánto mover cada servo
    delta_x = Kp_x * error_x
    delta_y = Kp_y * error_y

    # Actualizar posición
    servoPos[0] += delta_x
    servoPos[1] += delta_y

    # Limitar
    servoPos[0] = np.clip(servoPos[0], 0, 180)
    servoPos[1] = np.clip(servoPos[1], 75, 120)

    # Escribir en servos
    servo_x.write(servoPos[0])
    servo_y.write(servoPos[1])


# --- BUCLE PRINCIPAL ---
while True:
    ret, frame = cap.read()
    if not ret:
        break

    nuevos_centros = procesar_detecciones(frame)
    visibles = asociar_detecciones(nuevos_centros, umbral_distancia)

    if seguido_id is None and visibles:
        seguido_id = visibles[0][0]

    for idv, centro, x, y, w, h in visibles:
        posiciones_finales[idv] = centro
        posiciones_iniciales.setdefault(idv, centro)

    if seguido_id not in [v[0] for v in visibles] and posiciones_iniciales:
        for idv in reversed(list(posiciones_iniciales.keys())):
            if idv != seguido_id:
                seguido_id = idv
                break

    h, w = frame.shape[:2]
    zona_w = w // 4
    for i in range(1, 4):
        cv2.line(frame, (i * zona_w, 0), (i * zona_w, h), (200, 200, 200), 2)
    overlay = frame.copy()
    colores = [(0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 0, 0)]
    for i, col in enumerate(colores):
        cv2.rectangle(overlay, (i * zona_w, 0), ((i + 1) * zona_w, h), col, -1)
    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    etiquetas = ["Izquierda", "Centro-Izq", "Centro-Der", "Derecha"]
    for i, et in enumerate(etiquetas):
        cv2.putText(frame, et, (i * zona_w + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 2)

    if not args.no_boxes:
        for idv, centro, x, y, w_box, h_box in visibles:
            color = (0, 255, 0) if idv == seguido_id else (255, 0, 0)
            cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), color, 2)
            cv2.putText(frame, f"ID:{idv}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    for idv, centro, *_ in visibles:
        if idv == seguido_id:
            last_detection_time = time.time()
            zona_idx = centro[0] // zona_w
            zona = etiquetas[min(zona_idx, 3)]
            frame_num = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            seguimiento_log.append((frame_num, idv, zona))

            if args.modo_rotativa:
                actualizar_servos(*centro)
            break
        
    # Si no se detecta al objetivo por más de 5 segundos se reinicia la posición de los servos
    if args.modo_rotativa and time.time() - last_detection_time > timeout:
        servo_x.write(baseX)
        servo_y.write(baseY)
    out.write(frame)

    cv2.imshow("Seguimiento de persona", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break    

# --- LIMPIEZA ---
if args.modo_rotativa:
    board.exit()
cap.release()
out.release()
cv2.destroyAllWindows()

# --- GUARDAR CSV ---
with open(csv_filename, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Frame", "ID", "Zona"])
    w.writerows(seguimiento_log)

print(f"Video guardado en: {video_filename}")
print(f"Log guardado en : {csv_filename}")
