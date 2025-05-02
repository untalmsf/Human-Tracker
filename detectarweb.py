# track_script.py
import cv2
import torch
import numpy as np
import csv
import os
import warnings
import argparse

warnings.filterwarnings("ignore", message=".*autocast.*")

# --- PARSER DE ARGUMENTOS ---
parser = argparse.ArgumentParser(description="Person Tracker con YOLOv5")
parser.add_argument("--camera", type=int, help="Índice de cámara a usar")
parser.add_argument("--video", help="Archivo de video a procesar")
parser.add_argument("--out-base", required=True, help="Base de nombre para archivos de salida")
parser.add_argument("--no-boxes", action="store_true", help="Desactivar dibujo de bounding boxes")
args = parser.parse_args()

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

# --- CARGAR MODELO YOLOv5 ---
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')

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
            if x1 < x < x1 + w and y1 < y < y1 + h:
                seguido_id = idv
                break

cv2.namedWindow("Seguimiento de persona")
cv2.setMouseCallback("Seguimiento de persona", click)

# --- FUNCIONES AUXILIARES ---
def procesar_detecciones(imagen):
    results = model(imagen)
    detecciones = results.xyxy[0].cpu().numpy()
    output = []
    for x1, y1, x2, y2, conf, cls in detecciones:
        if int(cls)==0 and conf>0.5:
            w, h = x2-x1, y2-y1
            cx, cy = int(x1+w/2), int(y1+h/2)
            output.append(( (cx,cy), int(x1), int(y1), int(w), int(h) ))
    return output

def asociar_detecciones(nuevos, umbral):
    global siguiente_id
    visibles = []
    usados = set()
    for centro, x, y, w, h in nuevos:
        mejor_id, mejor_dist = None, float('inf')
        for idc, (cent_ant, *_) in candidatos.items():
            dist = np.hypot(centro[0]-cent_ant[0], centro[1]-cent_ant[1])
            if dist<mejor_dist and dist<umbral:
                mejor_dist, mejor_id = dist, idc
        if mejor_id is not None:
            candidatos[mejor_id] = (centro, x, y, w, h)
            visibles.append((mejor_id, centro, x, y, w, h))
        else:
            candidatos[siguiente_id] = (centro, x, y, w, h)
            visibles.append((siguiente_id, centro, x, y, w, h))
            siguiente_id += 1
    return visibles

# --- BUCLE PRINCIPAL ---
while True:
    ret, frame = cap.read()
    if not ret:
        break

    nuevos_centros = procesar_detecciones(frame)
    visibles = asociar_detecciones(nuevos_centros, umbral_distancia)

    # Selección automática inicial
    if seguido_id is None and visibles:
        seguido_id = visibles[0][0]

    # Actualizar posiciones
    for idv, centro, x, y, w, h in visibles:
        posiciones_finales[idv] = centro
        posiciones_iniciales.setdefault(idv, centro)

    # Si se pierde el seguido_id, cambiar a otro
    if seguido_id not in [v[0] for v in visibles] and posiciones_iniciales:
        for idv in reversed(list(posiciones_iniciales.keys())):
            if idv!=seguido_id:
                seguido_id = idv
                break

    # Dibujar zonas de interés
    h, w = frame.shape[:2]
    zona_w = w//4
    for i in range(1,4):
        cv2.line(frame, (i*zona_w,0),(i*zona_w,h),(200,200,200),2)
    overlay = frame.copy()
    colores = [(0,0,255),(0,255,255),(0,255,0),(255,0,0)]
    for i,col in enumerate(colores):
        cv2.rectangle(overlay,(i*zona_w,0),((i+1)*zona_w,h),col,-1)
    cv2.addWeighted(overlay,0.15,frame,0.85,0,frame)
    etiquetas = ["Izquierda","Centro-Izq","Centro-Der","Derecha"]
    for i,et in enumerate(etiquetas):
        cv2.putText(frame, et, (i*zona_w + 10,30), cv2.FONT_HERSHEY_SIMPLEX,0.6,(50,50,50),2)

    # Dibujar bounding boxes si se desea
    if not args.no_boxes:
        for idv, centro, x, y, w_box, h_box in visibles:
            color = (0,255,0) if idv==seguido_id else (255,0,0)
            cv2.rectangle(frame, (x,y),(x+w_box,y+h_box), color,2)
            cv2.putText(frame, f"ID:{idv}", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX,0.6,color,2)

    # Registrar posición del seguido_id
    for idv, centro, *_ in visibles:
        if idv==seguido_id:
            zona_idx = centro[0]//zona_w
            zona = etiquetas[min(zona_idx,3)]
            frame_num = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            seguimiento_log.append((frame_num, idv, zona))
            break

    out.write(frame)
    cv2.imshow("Seguimiento de persona", frame)
    if cv2.waitKey(1)&0xFF==ord('q'):
        break

# --- LIMPIEZA ---
cap.release()
out.release()
cv2.destroyAllWindows()

# --- GUARDAR CSV ---
with open(csv_filename, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Frame","ID","Zona"])
    w.writerows(seguimiento_log)

print(f"Video guardado en: {video_filename}")
print(f"Log guardado en : {csv_filename}")
