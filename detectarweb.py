import cv2
import torch
import numpy as np
import requests
import csv
import os  
import warnings
warnings.filterwarnings("ignore", message=".*autocast.*")

# Variables globales
seguido_id = None
clic_pos = None
siguiente_id = 0
candidatos = {}
posiciones_iniciales = {}
posiciones_finales = {}
seguimiento_log = []

def click(event, x, y, flags, param):
    global clic_pos, seguido_id, candidatos
    if event == cv2.EVENT_LBUTTONDOWN:
        clic_pos = (x, y)
        #print(f"Click en posición: {clic_pos}")
        for idv, (centro, x1, y1, w, h) in candidatos.items():
            #print(f"Chequeando ID {idv} en zona: ({x1}, {y1}, {x1+w}, {y1+h})")
            if x1 < x < x1 + w and y1 < y < y1 + h:
                seguido_id = idv
                #print(f"Persona seleccionada: ID {idv}")
                break

# Cargar modelo YOLOv5
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')

# Video
cap = cv2.VideoCapture("video.mp4")
cv2.namedWindow("Seguimiento de persona")
cv2.setMouseCallback("Seguimiento de persona", click)

umbral_distancia = 50
frames_perdido = 0
max_frames_perdido = 30

# Generar nombres únicos para los archivos de salida
def generar_nombre_unico(base, extension):
    i = 1
    nombre = f"{base}.{extension}"
    while os.path.exists(nombre):
        nombre = f"{base}_{i}.{extension}"
        i += 1
    return nombre

video_filename = generar_nombre_unico("output", "avi")
csv_filename = generar_nombre_unico("seguimiento", "csv")

# Archivo salida de video
out = cv2.VideoWriter(video_filename, cv2.VideoWriter_fourcc(*'XVID'), 30, (int(cap.get(3)), int(cap.get(4))))

def procesar_detecciones(imagen, model):
    results = model(imagen)
    detecciones = results.xyxy[0].cpu().numpy()
    nuevos_centros = []
    for deteccion in detecciones:
        confianza = deteccion[4]
        clase = int(deteccion[5])
        if clase == 0 and confianza > 0.5:
            x1, y1, x2, y2 = deteccion[:4]
            w, h = x2 - x1, y2 - y1
            centro = (int(x1 + w // 2), int(y1 + h // 2))
            nuevos_centros.append((centro, int(x1), int(y1), int(w), int(h)))
    return nuevos_centros

def asociar_detecciones(nuevos_centros, candidatos, siguiente_id):
    visibles = []
    usados = set()
    for centro, x, y, w, h in nuevos_centros:
        mejor_id = None
        mejor_distancia = float('inf')
        for id_candidato, (centro_guardado, *_resto) in candidatos.items():
            d = np.sqrt((centro[0] - centro_guardado[0])**2 + (centro[1] - centro_guardado[1])**2)
            if d < mejor_distancia and d < umbral_distancia:
                mejor_distancia = d
                mejor_id = id_candidato

        if mejor_id is not None:
            usados.add(mejor_id)
            candidatos[mejor_id] = (centro, x, y, w, h)
            visibles.append((mejor_id, centro, x, y, w, h))
        else:
            candidatos[siguiente_id] = (centro, x, y, w, h)
            visibles.append((siguiente_id, centro, x, y, w, h))
            siguiente_id += 1

    return visibles, siguiente_id

def procesar_frame(cap, model, candidatos, siguiente_id, seguido_id, frames_perdido, clic_pos, out):
    ret, imagen = cap.read()
    if not ret:
        return False, siguiente_id, seguido_id, frames_perdido, clic_pos

    nuevos_centros = procesar_detecciones(imagen, model)
    visibles, siguiente_id = asociar_detecciones(nuevos_centros, candidatos, siguiente_id)

    if seguido_id is None and len(visibles) > 0:
        seguido_id = visibles[0][0]
        #print(f"Seleccionando persona con ID {seguido_id} como seguida")

    frame_num = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
    for idv, centro, x, y, w, h in visibles:
        posiciones_finales[idv] = (centro[0], centro[1])
        if idv not in posiciones_iniciales:
            posiciones_iniciales[idv] = (centro[0], centro[1])

    if seguido_id is not None and seguido_id not in [v[0] for v in visibles]:
        #print(f"Persona con ID {seguido_id} no está visible. Cambiando a la última persona detectada.")
        if len(posiciones_iniciales) > 0:
            for idv in reversed(list(posiciones_iniciales.keys())):
                if idv != seguido_id:
                    seguido_id = idv
                    #print(f"Seleccionando persona con ID {seguido_id} como seguida")
                    break

    # Dibujar zonas
    ancho = imagen.shape[1]
    alto = imagen.shape[0]
    zona_w = ancho // 4

    for i in range(1, 4):
        x = i * zona_w
        cv2.line(imagen, (x, 0), (x, alto), (200, 200, 200), 2)

    overlay = imagen.copy()
    cv2.rectangle(overlay, (0, 0), (zona_w, alto), (0, 0, 255), -1)
    cv2.rectangle(overlay, (zona_w, 0), (2 * zona_w, alto), (0, 255, 255), -1)
    cv2.rectangle(overlay, (2 * zona_w, 0), (3 * zona_w, alto), (0, 255, 0), -1)
    cv2.rectangle(overlay, (3 * zona_w, 0), (ancho, alto), (255, 0, 0), -1)
    alpha = 0.15
    cv2.addWeighted(overlay, alpha, imagen, 1 - alpha, 0, imagen)

    cv2.putText(imagen, "Izquierda", (zona_w//4 - 30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 150), 2)
    cv2.putText(imagen, "Centro-Izq", (zona_w + zona_w//4 - 40, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 150), 2)
    cv2.putText(imagen, "Centro-Der", (2 * zona_w + zona_w//4 - 45, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 0), 2)
    cv2.putText(imagen, "Derecha", (3 * zona_w + zona_w//4 - 30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 0, 0), 2)

    # Dibujar bounding boxes
    for idv, centro, x, y, w, h in visibles:
        color = (0, 255, 0) if idv == seguido_id else (255, 0, 0)
        cv2.rectangle(imagen, (x, y), (x + w, y + h), color, 2)
        cv2.putText(imagen, f"ID: {idv}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Guardar zona del seguido_id si está visible
    for idv, centro, x, y, w, h in visibles:
        if idv == seguido_id:
            x_centro = centro[0]
            if x_centro < zona_w:
                zona = "Izquierda"
            elif x_centro < 2 * zona_w:
                zona = "Centro-Izquierda"
            elif x_centro < 3 * zona_w:
                zona = "Centro-Derecha"
            else:
                zona = "Derecha"
            seguimiento_log.append((frame_num, idv, zona))
            break

    out.write(imagen)
    cv2.imshow("Seguimiento de persona", imagen)

    return True, siguiente_id, seguido_id, frames_perdido, clic_pos

def main_loop():
    global clic_pos, seguido_id, siguiente_id, frames_perdido
    while True:
        continuar, siguiente_id, seguido_id, frames_perdido, clic_pos = procesar_frame(
            cap, model, candidatos, siguiente_id,
            seguido_id, frames_perdido, clic_pos, out
        )
        if not continuar or cv2.waitKey(1) & 0xFF == ord('q'):
            break

# Ejecutar
main_loop()
cap.release()
out.release()

# Guardar el seguimiento en un archivo CSV sin sobrescribir
with open(csv_filename, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Frame", "ID", "Zona"])
    writer.writerows(seguimiento_log)
