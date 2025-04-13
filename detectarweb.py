import cv2
import time

# Captura de video desde la cámara (0 es la cámara por defecto)
cap = cv2.VideoCapture(1)

# Cargamos el detector de cuerpos enteros de OpenCV
# detector = cv2.CascadeClassifier("haarcascade_fullbody.xml")
detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")



# Variables para seguimiento
seguido_id = None
siguiente_id = 0
candidatos = {}  # ID de persona → centro (x, y)

# Función para calcular distancia entre dos puntos
def distancia(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2) ** 0.5

while True:
    ret, imagen = cap.read()
    if not ret:
        break

    # Convertimos a escala de grises para detectar mejor
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

    # Detectamos cuerpos
    cuerpos = detector.detectMultiScale(gris, 1.1, 4)

    nuevos_centros = []

    # Calculamos el centro de cada cuerpo detectado
    for (x, y, w, h) in cuerpos:
        centro = (x + w // 2, y + h // 2)
        nuevos_centros.append((centro, x, y, w, h))

    # Asociamos los detectados con los candidatos anteriores
    visibles = []
    for id_candidato, centro_guardado in candidatos.items():
        for centro, x, y, w, h in nuevos_centros:
            if distancia(centro, centro_guardado) < 50:
                visibles.append((id_candidato, centro, x, y, w, h))
                break

    # Si el seguido actual ya no está visible, elegimos el último que entró
    if seguido_id not in [idv for idv, *_ in visibles]:
        for idv, centro, x, y, w, h in reversed(visibles):
            seguido_id = idv
            break

    # Si aún no seguimos a nadie, asignamos al último que entró
    if seguido_id is None and nuevos_centros:
        centro, x, y, w, h = nuevos_centros[-1]
        candidatos[siguiente_id] = centro
        seguido_id = siguiente_id
        siguiente_id += 1

    # Dibujamos al cuerpo seguido
    for idv, centro, x, y, w, h in visibles:
        if idv == seguido_id:
            candidatos[idv] = centro  # Actualizamos su posición
            cv2.rectangle(imagen, (x, y), (x + w, y + h), (0, 255, 0), 2)
            break  # Solo seguimos a uno

    # Mostramos el video
    cv2.imshow("Seguimiento de persona", imagen)

    # Presioná 'q' para salir
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Liberamos recursos
cap.release()
cv2.destroyAllWindows()
