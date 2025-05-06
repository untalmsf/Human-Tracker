import subprocess
import sys

def instalar_paquete(paquete):
    try:
        __import__(paquete)
    except ImportError:
        print(f"Instalando {paquete}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", paquete])

# Instalar librerías necesarias
instalar_paquete("pandas")
instalar_paquete("matplotlib")
instalar_paquete("numpy")
instalar_paquete("openpyxl")
instalar_paquete("pyfirmata2")
instalar_paquete("PIL")
instalar_paquete("csv")
instalar_paquete("ultralytics")
instalar_paquete("cv2")

import os, subprocess, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from serial.tools import list_ports

class TrackerGUI(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack(padx=10, pady=10)
        self.create_widgets()

    def create_widgets(self):
        # Etiqueta para centrar a lo alto
        tk.Label(self, text="", padx=50, pady=50).grid(row=0, column=0, sticky="w")

        # Redimensionar imagen
        image = Image.open("logo.png")
        image = image.resize((300, 300), Image.Resampling.LANCZOS)
        self.logo_img = ImageTk.PhotoImage(image)
        tk.Label(self, image=self.logo_img, padx=10, pady=10).grid(row=1, column=0, columnspan=4, pady=10)


        # selecccionar modos
        self.input_mode = tk.StringVar(value="camera")
        tk.Radiobutton(self, text="Camara", variable=self.input_mode, value="camera", command=self.on_mode_change).grid(row=2, column=0, pady=(5, 0), sticky="w")
        tk.Radiobutton(self, text="Camara Rotativa", variable=self.input_mode, value="CamaraRot", command=self.on_mode_change).grid(row=3, column=0, pady=(5, 0), sticky="w")
        tk.Radiobutton(self, text="Video", variable=self.input_mode, value="video", command=self.on_mode_change).grid(row=5, column=0, pady=(5, 0), sticky="w")

        # Seleccionar camara
        tk.Label(self, text="Camara:").grid(row=2, column=1, pady=(5, 0), sticky="e")
        self.cam_index = tk.Spinbox(self, from_=0, to=2, width=5)
        self.cam_index.grid(row=2, column=2, pady=(5, 0), sticky="w")

        # Ajustes de la cámara rotativa
        self.label_com = tk.Label(self, text="Puerto COM:")
        self.label_com.grid(row=3, column=1, pady=(5, 0), sticky="e")
        self.combo_com = ttk.Combobox(self, values=self.get_arduino_ports(), width=15)
        self.combo_com.grid(row=3, column=2, pady=(5, 0), sticky="w")

        # Seleccionar video
        self.video_path = tk.Entry(self, width=30, state="disabled")
        self.video_path.grid(row=5, column=1, columnspan=2, pady=(5, 0), sticky="w")
        self.btn_browse = tk.Button(self, text="Buscar...", command=self.browse_video, state="disabled")
        self.btn_browse.grid(row=5, column=3, pady=(5, 0))

        # Nombre de salida
        tk.Label(self, text="Nombre del video:").grid(row=6, column=0, pady=(5, 0), sticky="e")
        self.out_base = tk.Entry(self, width=20)
        self.out_base.insert(0, "output")
        self.out_base.grid(row=6, column=1, columnspan=2, pady=(5, 0), sticky="w")

        # Checkbox: draw boxes
        self.draw_boxes = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Bounding boxes", variable=self.draw_boxes).grid(row=7, column=0, columnspan=3, pady=(5, 0), sticky="w")

        # Boton de comenzar
        self.btn_start = tk.Button(self, text="Procesar", command=self.start_tracking)
        self.btn_start.grid(row=8, column=0, columnspan=4, pady=10)

        # Botón para analizar archivo CSV
        self.btn_analyze = tk.Button(self, text="Analizar CSV", command=self.analyze_csv)
        self.btn_analyze.grid(row=9, column=0, columnspan=4, pady=10)
        
        # Etiqueta para centrar a lo alto
        tk.Label(self, text="", padx=20, pady=20).grid(row=10, column=0, sticky="w")
        
        # Untref Logo
        image2 = Image.open("untrefLogo.jpg")
        image2 = image2.resize((250, 100), Image.Resampling.LANCZOS)
        self.logo_img2 = ImageTk.PhotoImage(image2)
        tk.Label(self, image=self.logo_img2, padx=10, pady=10).grid(row=11, column=0, columnspan=4, pady=10)

        self.on_mode_change()

    def on_mode_change(self):
        mode = self.input_mode.get()
        if mode == "camera":
            self.cam_index.config(state="normal")
            self.video_path.config(state="disabled")
            self.btn_browse.config(state="disabled")

            # Desactivar rotativa
            self.combo_com.config(state="disabled")

        elif mode == "CamaraRot":
            self.cam_index.config(state="normal")
            self.video_path.config(state="disabled")
            self.btn_browse.config(state="disabled")

            # Activar rotativa
            self.combo_com.config(state="readonly")
            self.combo_com['values'] = self.get_arduino_ports()

        else:  # modo video
            self.cam_index.config(state="disabled")
            self.video_path.config(state="normal")
            self.btn_browse.config(state="normal")

            # Desactivar rotativa
            self.combo_com.config(state="disabled")



    def browse_video(self):
        path = filedialog.askopenfilename(title="Select video file",
                                        filetypes=[("MP4 files","*.mp4"),("All files","*.*")])
        if path:
            self.video_path.delete(0, tk.END)
            self.video_path.insert(0, path)
        
    def get_arduino_ports(self):
        ports = list_ports.comports()
        arduino_ports = []

        for port in ports:
            if "Arduino" in port.description or "CH340" in port.description or "ttyUSB" in port.device:
                arduino_ports.append(port.device)

        # Si no se detecta ninguno, mostrar todos por si acaso
        if not arduino_ports:
            arduino_ports = [port.device for port in ports]

        return arduino_ports

    def start_tracking(self):
        mode = self.input_mode.get()
        out_base = self.out_base.get().strip()
        if not out_base:
            messagebox.showerror("Error", "Debe ingresar un nombre base para la salida.")
            return
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "detectarweb.py")

        cmd = ["python", script_path, "--out-base", out_base]

        if mode == "camera":
            idx = int(self.cam_index.get())
            cmd += ["--camera", str(idx)]
        elif mode == "CamaraRot":
            idx = int(self.cam_index.get())
            port = self.combo_com.get().strip()

            if not port:
                messagebox.showerror("Error", "Debe seleccionar un puerto COM para el Arduino.")
                return

            cmd += ["--camera", str(idx), "--modo-rotativa", "--com", port]
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
    root.title("Sistema de Seguimiento de Personas")
    
    # Obtener el tamaño de la pantalla
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    root.geometry(f"{screen_width}x{screen_height}")  # Tamaño inicial de la ventana
    
    root.lift()
    root.focus_force()
    root.state("zoomed")
    
    app = TrackerGUI(master=root)
    root.mainloop()
