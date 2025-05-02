import pandas as pd
import matplotlib.pyplot as plt

# Leer el CSV sin encabezado y nombrar columnas
try:
    df = pd.read_csv("seguimiento.csv", encoding="latin1", header=None, names=["Frame", "ID", "Zona"])
except FileNotFoundError:
    print("No se encontró el archivo 'seguimiento.csv'. Verificá el nombre o la ruta.")
    exit()

# Limpiar espacios y estandarizar nombres
df["Zona"] = df["Zona"].str.strip()

# Mapear nombres de zonas
mapeo_zonas = {
    "Izquierda": "Izquierda",
    "Centro-Izq": "Centro Izquierda",
    "Centro-Der": "Centro Derecha",
    "Derecha": "Derecha"
}
df["Zona"] = df["Zona"].map(mapeo_zonas)
df = df[df["Zona"].notna()]

# ========================
# ANÁLISIS 1: Personas únicas por zona
# ========================
df_sin_duplicados = df.drop_duplicates(subset=["ID", "Zona"])
conteo_unicos = df_sin_duplicados["Zona"].value_counts().reindex(
    ["Izquierda", "Centro Izquierda", "Centro Derecha", "Derecha"], fill_value=0
)

# ========================
# ANÁLISIS 2: Cantidad total de apariciones por zona
# ========================
conteo_total = df["Zona"].value_counts().reindex(
    ["Izquierda", "Centro Izquierda", "Centro Derecha", "Derecha"], fill_value=0
)

# ========================
# ANÁLISIS 7: Tiempo estimado en cada zona por persona (cantidad de frames)
# ========================
tiempo_por_zona = df.groupby(["ID", "Zona"]).size().reset_index(name="Frames")

# ========================
# EXPORTAR A EXCEL
# ========================
with pd.ExcelWriter("analisis_zonas_completo.xlsx") as writer:
    conteo_unicos.to_frame(name="Personas únicas").to_excel(writer, sheet_name="Personas únicas por zona")
    conteo_total.to_frame(name="Apariciones").to_excel(writer, sheet_name="Apariciones por zona")
    tiempo_por_zona.to_excel(writer, sheet_name="Frames por zona por ID", index=False)

print("📁 Archivo Excel 'analisis_zonas_completo.xlsx' generado con éxito.")

# ========================
# GRÁFICO COMPARATIVO
# ========================
fig, axs = plt.subplots(2, 1, figsize=(8, 8))

# Personas únicas
axs[0].bar(conteo_unicos.index, conteo_unicos.values, color='skyblue')
axs[0].set_title("Personas únicas por zona")
axs[0].set_ylabel("Cantidad de personas")

# Apariciones totales
axs[1].bar(conteo_total.index, conteo_total.values, color='salmon')
axs[1].set_title("Apariciones totales por zona")
axs[1].set_ylabel("Cantidad de apariciones")

for ax in axs:
    ax.set_xticks(range(len(conteo_total.index)))
    ax.set_xticklabels(conteo_total.index, rotation=15)

plt.tight_layout()
plt.savefig("analisis_zonas_completo.png", dpi=300)
plt.show()
