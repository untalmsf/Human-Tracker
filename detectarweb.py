import cv2

cap = cv2.VideoCapture("C:\\Users\\MARK¡TO\\Desktop\\2025\\pruebas\\video.mp4")

detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
if detector.empty():
    print("❌ Error: no se pudo cargar el clasificador.")
    exit()

seguido_id = None
siguiente_id = 0
candidatos = {}  # ID → centro
frames_perdido = 0
max_frames_perdido = 2
umbral_distancia = 80

def distancia(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2) ** 0.5

while True:
    ret, imagen = cap.read()
    if not ret:
        break

    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    cuerpos = detector.detectMultiScale(gris, 1.1, 4)

    nuevos_centros = []
    for (x, y, w, h) in cuerpos:
        centro = (x + w // 2, y + h // 2)
        nuevos_centros.append((centro, x, y, w, h))

    visibles = []

    # Para cada nuevo centro, vemos si ya existe uno cercano en candidatos
    usados = set()
    for centro, x, y, w, h in nuevos_centros:
        mejor_id = None
        mejor_distancia = float('inf')

        for id_candidato, centro_guardado in candidatos.items():
            if id_candidato in usados:
                continue
            d = distancia(centro, centro_guardado)
            if d < mejor_distancia and d < umbral_distancia:
                mejor_distancia = d
                mejor_id = id_candidato

        if mejor_id is not None:
            usados.add(mejor_id)
            candidatos[mejor_id] = centro
            visibles.append((mejor_id, centro, x, y, w, h))
        else:
            # nuevo ID
            candidatos[siguiente_id] = centro
            visibles.append((siguiente_id, centro, x, y, w, h))
            siguiente_id += 1

    # Seguimiento
    visibles_ids = [idv for idv, *_ in visibles]
    if seguido_id is not None and seguido_id in visibles_ids:
        frames_perdido = 0
    else:
        frames_perdido += 1
        if frames_perdido >= max_frames_perdido:
            seguido_id = None

    # Si no hay seguido actual, elegimos el más reciente
    if seguido_id is None and visibles:
        seguido_id = visibles[-1][0]
        frames_perdido = 0

    # Dibujamos todos los rectángulos
    for idv, centro, x, y, w, h in visibles:
        color = (0, 255, 0) if idv == seguido_id else (255, 0, 0)
        cv2.rectangle(imagen, (x, y), (x + w, y + h), color, 2)
        cv2.putText(imagen, f"ID: {idv}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imshow("Seguimiento de persona", imagen)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
