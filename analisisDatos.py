import pandas as pd
import matplotlib.pyplot as plt

# Leer el CSV sin encabezado y nombrar columnas
try:
    df = pd.read_csv("seguimiento.csv", encoding="latin1", header=None, names=["Frame", "ID", "Zona"])
except FileNotFoundError:
    print("No se encontró el archivo 'seguimiento.csv'. Verificá el nombre o la ruta.")
    exit()

# Limpiar espacios en la columna "Zona"
df["Zona"] = df["Zona"].str.strip()

# Tomar solo la última zona en la que aparece cada ID
df_ultima_zona = df.drop_duplicates(subset="ID", keep="last")

# Mapear nombres para mostrar como querés
mapeo_zonas = {
    "Izquierda": "Izquierda",
    "Centro-Izquierda": "Centro Izquierda",
    "Centro-Derecha": "Centro Derecha",
    "Derecha": "Derecha"
}
df_ultima_zona["Zona"] = df_ultima_zona["Zona"].map(mapeo_zonas)

# Definir orden de zonas y contar
zonas_ordenadas = ["Izquierda", "Centro Izquierda", "Centro Derecha", "Derecha"]
conteo = df_ultima_zona["Zona"].value_counts().reindex(zonas_ordenadas, fill_value=0)

# Mostrar resultados
print("Número de personas en cada zona (último registro por ID):")
for zona, cantidad in conteo.items():
    print(f"{zona}: {cantidad} personas")

# Graficar
plt.bar(conteo.index, conteo.values, color=['blue', 'red', 'black', 'green'])
plt.xlabel("Zona")
plt.ylabel("Número de personas")
plt.xticks(rotation=15)
plt.tight_layout()
plt.show()
