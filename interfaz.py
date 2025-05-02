import cv2, os, subprocess, tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt

class TrackerGUI(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack(padx=10, pady=10)
        self.create_widgets()

    def create_widgets(self):

        self.input_mode = tk.StringVar(value="camera")
        tk.Radiobutton(self, text="Camara", variable=self.input_mode, value="camera", command=self.on_mode_change).grid(row=0, column=0, sticky="w")
        tk.Radiobutton(self, text="Video", variable=self.input_mode, value="video", command=self.on_mode_change).grid(row=1, column=0, sticky="w")

        # Seleccionar camara
        tk.Label(self, text="Camara:").grid(row=0, column=1, sticky="e")
        self.cam_index = tk.Spinbox(self, from_=0, to=5, width=5)
        self.cam_index.grid(row=0, column=2, sticky="w")

        # Seleccionar video
        self.video_path = tk.Entry(self, width=30, state="disabled")
        self.video_path.grid(row=1, column=1, columnspan=2, sticky="w")
        self.btn_browse = tk.Button(self, text="Buscar...", command=self.browse_video, state="disabled")
        self.btn_browse.grid(row=1, column=3)

        # Nombre de salida
        tk.Label(self, text="Nombre del video:").grid(row=2, column=0, sticky="e")
        self.out_base = tk.Entry(self, width=20)
        self.out_base.insert(0, "output")
        self.out_base.grid(row=2, column=1, columnspan=2, sticky="w")

        # Checkbox: draw boxes
        self.draw_boxes = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Bounding boxes", variable=self.draw_boxes).grid(row=3, column=0, columnspan=3, sticky="w")

        # Boton de comenzar
        self.btn_start = tk.Button(self, text="Procesar", command=self.start_tracking)
        self.btn_start.grid(row=4, column=0, columnspan=4, pady=10)

        # Botón para analizar archivo CSV
        self.btn_analyze = tk.Button(self, text="Analizar CSV", command=self.analyze_csv)
        self.btn_analyze.grid(row=5, column=0, columnspan=4, pady=10)

    def on_mode_change(self):
        mode = self.input_mode.get()
        if mode == "camera":
            self.cam_index.config(state="normal")
            self.video_path.config(state="disabled")
            self.btn_browse.config(state="disabled")
        else:
            self.cam_index.config(state="disabled")
            self.video_path.config(state="normal")
            self.btn_browse.config(state="normal")

    def browse_video(self):
        path = filedialog.askopenfilename(title="Select video file",
                                        filetypes=[("MP4 files","*.mp4"),("All files","*.*")])
        if path:
            self.video_path.delete(0, tk.END)
            self.video_path.insert(0, path)

    def start_tracking(self):
        mode = self.input_mode.get()
        out_base = self.out_base.get().strip()
        if not out_base:
            messagebox.showerror("Error", "Debe ingresar un nombre base para la salida.")
            return

        # Ruta genérica al script en la misma carpeta que este gui.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "detectarweb.py")

        cmd = ["python", script_path, "--out-base", out_base]
        if mode == "camera":
            idx = int(self.cam_index.get())
            cmd += ["--camera", str(idx)]
        else:
            vid = self.video_path.get().strip()
            if not vid or not os.path.isfile(vid):
                messagebox.showerror("Error", "Debe seleccionar un video válido.")
                return
            cmd += ["--video", vid]

        if not self.draw_boxes.get():
            cmd += ["--no-boxes"]

        try:
            proc = subprocess.Popen(cmd)
            proc.wait()
        except Exception as e:
            messagebox.showerror("Error al lanzar", str(e))
            return

        # Buscar salida .avi en carpeta del script
        out_file = None
        for f in os.listdir(script_dir):
            if f.startswith(out_base) and f.endswith(".avi"):
                out_file = os.path.join(script_dir, f)
                break

        if not out_file:
            messagebox.showerror("Error", "No encontré el video de salida.")
            return

    def analyze_csv(self):
        # Pedir el archivo CSV generado
        file_path = filedialog.askopenfilename(title="Seleccionar archivo CSV",
                                               filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not file_path:
            return

        try:
            df = pd.read_csv(file_path, encoding="latin1", header=None, names=["Frame", "ID", "Zona"])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el archivo CSV: {str(e)}")
            return

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
        output_excel = file_path.replace(".csv", "_analisis.xlsx")
        with pd.ExcelWriter(output_excel) as writer:
            conteo_unicos.to_frame(name="Personas únicas").to_excel(writer, sheet_name="Personas únicas por zona")
            conteo_total.to_frame(name="Apariciones").to_excel(writer, sheet_name="Apariciones por zona")
            tiempo_por_zona.to_excel(writer, sheet_name="Frames por zona por ID", index=False)

        messagebox.showinfo("Éxito", f"Análisis completado y guardado como {output_excel}.")

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
        graph_path = file_path.replace(".csv", "_grafico.png")
        plt.savefig(graph_path, dpi=300)
        plt.show()
        messagebox.showinfo("Gráfico generado", f"Gráfico guardado como {graph_path}.")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Configuración de Person‑Tracker")
    app = TrackerGUI(master=root)
    root.mainloop()
