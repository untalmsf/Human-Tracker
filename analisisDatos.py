import pandas as pd
import matplotlib.pyplot as plt

# Leer el CSV sin encabezado y nombrar columnas
try:
    df = pd.read_csv("seguimiento.csv", encoding="latin1", header=None, names=["Frame", "ID", "Zona"])
except FileNotFoundError:
    print("No se encontró el archivo 'seguimiento_2.csv'. Verificá el nombre o la ruta.")
    exit()

# Limpiar espacios en la columna "Zona"
df["Zona"] = df["Zona"].str.strip()

# Eliminar zonas inválidas o vacías si las hubiera
df = df[df["Zona"].notna() & (df["Zona"] != "")]

# Mapear nombres para mostrar como querés
mapeo_zonas = {
    "Izquierda": "Izquierda",
    "Centro-Izquierda": "Centro Izquierda",
    "Centro-Derecha": "Centro Derecha",
    "Derecha": "Derecha"
}
df["Zona"] = df["Zona"].map(mapeo_zonas)

# Eliminar filas con zonas no reconocidas
df = df[df["Zona"].notna()]

# Eliminar duplicados de combinaciones ID-Zona (cuenta solo una vez por zona por ID)
df_sin_duplicados = df.drop_duplicates(subset=["ID", "Zona"])

# Contar cuántos IDs únicos hay por zona
conteo = df_sin_duplicados["Zona"].value_counts().reindex(
    ["Izquierda", "Centro Izquierda", "Centro Derecha", "Derecha"],
    fill_value=0
)

# Mostrar resultados
print("Número de personas únicas por zona (sin repetir por zona por ID):")
for zona, cantidad in conteo.items():
    print(f"{zona}: {cantidad} personas")

# Graficar
plt.bar(conteo.index, conteo.values, color=['blue', 'red', 'black', 'green'])
plt.xlabel("Zona")
plt.ylabel("Número de personas")
plt.xticks(rotation=15)
plt.tight_layout()
plt.show()
