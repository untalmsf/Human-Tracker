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
        tk.Label(self, text="", padx=50, pady=50).grid(row=0, column=0, sticky="w")

        image = Image.open("logo.png")
        image = image.resize((300, 300), Image.Resampling.LANCZOS)
        self.logo_img = ImageTk.PhotoImage(image)
        tk.Label(self, image=self.logo_img, padx=10, pady=10).grid(row=1, column=0, columnspan=4, pady=10)

        self.input_mode = tk.StringVar(value="camera")
        tk.Radiobutton(self, text="Camara", variable=self.input_mode, value="camera", command=self.on_mode_change).grid(row=2, column=0, pady=(5, 0), sticky="w")
        tk.Radiobutton(self, text="Camara Rotativa", variable=self.input_mode, value="CamaraRot", command=self.on_mode_change).grid(row=3, column=0, pady=(5, 0), sticky="w")
        tk.Radiobutton(self, text="Video", variable=self.input_mode, value="video", command=self.on_mode_change).grid(row=5, column=0, pady=(5, 0), sticky="w")

        tk.Label(self, text="Camara:").grid(row=2, column=1, pady=(5, 0), sticky="e")
        self.cam_index = tk.Spinbox(self, from_=0, to=2, width=5)
        self.cam_index.grid(row=2, column=2, pady=(5, 0), sticky="w")

        self.label_com = tk.Label(self, text="Puerto COM:")
        self.label_com.grid(row=3, column=1, pady=(5, 0), sticky="e")
        self.combo_com = ttk.Combobox(self, values=self.get_arduino_ports(), width=15)
        self.combo_com.grid(row=3, column=2, pady=(5, 0), sticky="w")

        self.video_path = tk.Entry(self, width=30, state="disabled")
        self.video_path.grid(row=5, column=1, columnspan=2, pady=(5, 0), sticky="w")
        self.btn_browse = tk.Button(self, text="Buscar...", command=self.browse_video, state="disabled")
        self.btn_browse.grid(row=5, column=3, pady=(5, 0))

        tk.Label(self, text="Nombre del video:").grid(row=6, column=0, pady=(5, 0), sticky="e")
        self.out_base = tk.Entry(self, width=20)
        self.out_base.insert(0, "output")
        self.out_base.grid(row=6, column=1, columnspan=2, pady=(5, 0), sticky="w")

        tk.Label(self, text="FPS:").grid(row=7, column=0, pady=(5, 0), sticky="e")
        self.fps_entry = tk.Entry(self, width=10)
        self.fps_entry.insert(0, "30")
        self.fps_entry.grid(row=7, column=1, pady=(5, 0), sticky="w")

        tk.Label(self, text="Resolución:").grid(row=8, column=0, pady=(5, 0), sticky="e")
        self.resolution_combo = ttk.Combobox(self, values=["640x480", "1280x720", "1920x1080"], width=15)
        self.resolution_combo.set("640x480")
        self.resolution_combo.grid(row=8, column=1, pady=(5, 0), sticky="w")

        self.draw_boxes = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Bounding boxes", variable=self.draw_boxes).grid(row=9, column=0, columnspan=3, pady=(5, 0), sticky="w")

        self.btn_start = tk.Button(self, text="Procesar", command=self.start_tracking)
        self.btn_start.grid(row=10, column=0, columnspan=4, pady=10)

        self.btn_analyze = tk.Button(self, text="Analizar CSV", command=self.analyze_csv)
        self.btn_analyze.grid(row=11, column=0, columnspan=4, pady=10)

        tk.Label(self, text="", padx=20, pady=20).grid(row=12, column=0, sticky="w")

        image2 = Image.open("untrefLogo.jpg")
        image2 = image2.resize((250, 100), Image.Resampling.LANCZOS)
        self.logo_img2 = ImageTk.PhotoImage(image2)
        tk.Label(self, image=self.logo_img2, padx=10, pady=10).grid(row=13, column=0, columnspan=4, pady=10)

        self.on_mode_change()

    def on_mode_change(self):
        mode = self.input_mode.get()
        if mode == "camera":
            self.cam_index.config(state="normal")
            self.video_path.config(state="disabled")
            self.btn_browse.config(state="disabled")
            self.combo_com.config(state="disabled")
        elif mode == "CamaraRot":
            self.cam_index.config(state="normal")
            self.video_path.config(state="disabled")
            self.btn_browse.config(state="disabled")
            self.combo_com.config(state="readonly")
            self.combo_com['values'] = self.get_arduino_ports()
        else:
            self.cam_index.config(state="disabled")
            self.video_path.config(state="normal")
            self.btn_browse.config(state="normal")
            self.combo_com.config(state="disabled")

    def browse_video(self):
        path = filedialog.askopenfilename(title="Select video file", filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")])
        if path:
            self.video_path.delete(0, tk.END)
            self.video_path.insert(0, path)

    def get_arduino_ports(self):
        ports = list_ports.comports()
        arduino_ports = [port.device for port in ports if "Arduino" in port.description or "CH340" in port.description or "ttyUSB" in port.device]
        if not arduino_ports:
            arduino_ports = [port.device for port in ports]
        return arduino_ports

    def start_tracking(self):
        mode = self.input_mode.get()
        out_base = self.out_base.get().strip()
        fps = self.fps_entry.get().strip()
        resolution = self.resolution_combo.get().strip()

        if not out_base:
            messagebox.showerror("Error", "Debe ingresar un nombre base para la salida.")
            return

        if not fps.isdigit():
            messagebox.showerror("Error", "FPS debe ser un número entero.")
            return

        try:
            width, height = map(int, resolution.split('x'))
        except ValueError:
            messagebox.showerror("Error", "La resolución seleccionada es inválida.")
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "detectarweb.py")

        cmd = ["python", script_path, "--out-base", out_base, "--fps", fps, "--resolution", resolution]

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

        out_file = None
        for f in os.listdir(script_dir):
            if f.startswith(out_base) and f.endswith(".avi"):
                out_file = f
                break

        if out_file:
            messagebox.showinfo("Video procesado", f"Video procesado correctamente. Archivo de salida: {out_file}")
        else:
            messagebox.showerror("Error", "No se generó un archivo de salida.")

    def analyze_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        try:
            df = pd.read_csv(file_path)
            df.head()
            plt.figure(figsize=(10, 6))
            df.plot(kind="line")
            plt.show()
        except Exception as e:
            messagebox.showerror("Error al procesar archivo", str(e))

root = tk.Tk()
app = TrackerGUI(master=root)
app.mainloop()



