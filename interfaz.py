import os, subprocess, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from serial.tools import list_ports
import sys
import platform
from detectarweb import main as detectarweb_main

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

class TrackerGUI(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        
    def get_url_type(self, url):
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        elif "earthcam.com" in url:
            return "earthcam"
        else:
            return "otro"

    def on_preset_change(self, event):
        selected_name = self.youtube_presets.get()
        selected_url = self.youtube_options.get(selected_name, "")

        self.youtube_url.config(state="normal")
        self.youtube_url.delete(0, tk.END)
        self.youtube_url.insert(0, selected_url)

        if selected_name == "Personalizado":
            self.youtube_url.config(state="normal")
        else:
            self.youtube_url.config(state="disabled")
        

    def create_widgets(self):

        canvas = tk.Canvas(self.master)
        scrollbar = tk.Scrollbar(self.master, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        scrollable_frame = tk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.scrollable_frame = scrollable_frame

        window = canvas.create_window((0, 0), window=scrollable_frame, anchor="n")

        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1*(event.delta/120)), "units"))

        def center_scrollable(event):
            canvas_width = event.width
            frame_width = scrollable_frame.winfo_reqwidth()
            x = max((canvas_width - frame_width) // 2, 0)
            canvas.coords(window, x, 0)

        canvas.bind("<Configure>", center_scrollable)


        tk.Label(scrollable_frame, text="", padx=50, pady=10).grid(row=0, column=0, sticky="w")
        image = Image.open(resource_path("logo.png")).resize((300, 300))
        self.logo_img = ImageTk.PhotoImage(image)
        tk.Label(scrollable_frame, image=self.logo_img).grid(row=1, column=0, columnspan=4, pady=5)

        tk.Label(scrollable_frame, text="Human Tracker", font=("Arial", 24)).grid(row=2, column=0, columnspan=4, pady=5)
        
        # Selección de modo de entrada
        tk.Label(scrollable_frame, text="Modo de funcionamiento", font=("Arial", 18)).grid(row=3, column=0, pady=5, sticky="w", columnspan=4)

        self.input_mode = tk.StringVar(value="camera")
        tk.Radiobutton(scrollable_frame, text="Camara", variable=self.input_mode, value="camera", command=self.on_mode_change).grid(row=4, column=0, sticky="w")
        tk.Label(scrollable_frame, text="Camara Rotativa").grid(row=5, column=0, sticky="w" ,padx=20)
        tk.Radiobutton(scrollable_frame, text="Camara publica", variable=self.input_mode, value="youtube", command=self.on_mode_change).grid(row=6, column=0, sticky="w")
        tk.Radiobutton(scrollable_frame, text="Video", variable=self.input_mode, value="video", command=self.on_mode_change).grid(row=7, column=0, sticky="w")

        # Parametros de camara
        self.cam_index = tk.Spinbox(scrollable_frame, from_=0, to=4, width=5)
        self.cam_index.grid(row=4, column=1, sticky="w")

        # Parametros de camara secundaria y arduino
        self.cam_index_sec = tk.Spinbox(scrollable_frame, from_=0, to=4, width=5)
        self.cam_index_sec.grid(row=5, column=1, sticky="w")
        self.label_com = tk.Label(scrollable_frame, text="Puerto COM:").grid(row=5, column=2, sticky="e")
        self.combo_com = ttk.Combobox(scrollable_frame, values=self.get_arduino_ports(), width=15)
        self.combo_com.grid(row=5, column=3, sticky="w")

        # Parametros de video de youtube
        self.youtube_options = {
            "Personalizado": "",
            "Times Square": "https://www.youtube.com/watch?v=rnXIjl_Rzy4",
            "Pinamar": "https://www.youtube.com/watch?v=VUODMJsRM9E",
            "Deadwood": "https://www.youtube.com/watch?v=IkxxNB-3HEw",
            "Mundo": "https://www.youtube.com/watch?v=z7SiAaN4ogw"
        }

        self.youtube_presets = ttk.Combobox(scrollable_frame, state="readonly", width=27)
        self.youtube_presets['values'] = list(self.youtube_options.keys())
        self.youtube_presets.set("Personalizado")
        self.youtube_presets.grid(row=6, column=1, sticky="w")
        self.youtube_presets.bind("<<ComboboxSelected>>", self.on_preset_change)

        tk.Label(scrollable_frame, text="URL:").grid(row=6, column=2, sticky="e")
        self.youtube_url = tk.Entry(scrollable_frame, width=30, state="disabled")
        self.youtube_url.grid(row=6, column=3, sticky="w")

        # Parametros de video externo
        self.video_path = tk.Entry(scrollable_frame, width=30, state="disabled")
        self.video_path.grid(row=7, column=1, sticky="w")
        self.btn_browse = tk.Button(scrollable_frame, text="Buscar...", command=self.browse_video, state="disabled")
        self.btn_browse.grid(row=7, column=2)
        
        # Botón [-]/[+] y título en la misma línea, pegado a la izquierda
        self.btn_toggle = tk.Button(scrollable_frame, text="[-]", width=5, command=self.toggle_avanzado)
        self.btn_toggle.grid(row=8, column=0,  padx=(0, 2))
        tk.Label(scrollable_frame, text="Funciones avanzadas", font=("Arial", 18)).grid(row=8, column=1, columnspan=3, sticky="w", pady=5)

        # ⬇ Frame que se podrá ocultar 
        self.avanzado_frame = tk.Frame(scrollable_frame)
        self.avanzado_frame.grid(row=9, column=0, columnspan=4, sticky="w")

        # --- Dentro de avanzado_frame ---
        tk.Label(self.avanzado_frame, text="Nombre del video:").grid(row=0, column=0, sticky="e", pady=2)
        self.out_base = tk.Entry(self.avanzado_frame, width=20)
        self.out_base.insert(0, "output")
        self.out_base.grid(row=0, column=1, columnspan=2, sticky="w", pady=2)

        tk.Label(self.avanzado_frame, text="Sencibilidad X:").grid(row=0, column=2, sticky="e", pady=2)
        gainX = tk.StringVar(self.master)
        gainX.set("1.0")
        self.gainX_entry = tk.Spinbox(self.avanzado_frame, width=10, from_=0, to=100, increment=0.001, format="%.3f", textvariable=gainX)
        self.gainX_entry.grid(row=0, column=3, sticky="w", pady=2)

        tk.Label(self.avanzado_frame, text="FPS:").grid(row=1, column=0, sticky="e", pady=2)
        fps = tk.StringVar(self.master)
        fps.set("30")
        self.fps_entry = tk.Spinbox(self.avanzado_frame, width=10, from_=0, to=100, textvariable=fps)
        self.fps_entry.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(self.avanzado_frame, text="Sencibilidad Y:").grid(row=1, column=2, sticky="e", pady=2)
        gainY = tk.StringVar(self.master)
        gainY.set("1.0")
        self.gainY_entry = tk.Spinbox(self.avanzado_frame, width=10, from_=0.0, to=120.0, increment=0.001, format="%.3f", textvariable=gainY)
        self.gainY_entry.grid(row=1, column=3, sticky="w", pady=2)

        tk.Label(self.avanzado_frame, text="Resolución:").grid(row=2, column=0, sticky="e", pady=2)
        self.resolution_combo = ttk.Combobox(self.avanzado_frame, values=["640x480", "1280x720", "1800x900"], width=15)
        self.resolution_combo.set("640x480")
        self.resolution_combo.grid(row=2, column=1, sticky="w", pady=2)

        tk.Label(self.avanzado_frame, text="Zoom (%):").grid(row=2, column=2, sticky="e", pady=2)
        zoom_value = tk.StringVar(self.master)
        zoom_value.set("100")  # 100% = sin zoom
        self.zoom_slider = tk.Scale(self.avanzado_frame, from_=100, to=200, resolution=1, orient="horizontal", variable=zoom_value)
        self.zoom_slider.grid(row=2, column=3)

        # Confianza mínima
        lbl_conf = tk.Label(self.avanzado_frame, text="Confianza mínima de persona:")
        lbl_conf.grid(row=3, column=0, sticky="e", pady=2)

        self.conf_threshold = tk.Spinbox(self.avanzado_frame, from_=0.0, to=100.0, increment=1, width=10)
        self.conf_threshold.delete(0, "end")
        self.conf_threshold.insert(0, "40")
        self.conf_threshold.grid(row=3, column=1, sticky="w", pady=2)

        # Base del servo x
        lbl_servo_x = tk.Label(self.avanzado_frame, text="Base del servo X:")
        lbl_servo_x.grid(row=3, column=2, sticky="e", pady=2)

        self.servo_base_x = tk.Spinbox(self.avanzado_frame, from_=0, to=180, width=10)
        self.servo_base_x.delete(0, "end")
        self.servo_base_x.insert(0, "80")
        self.servo_base_x.grid(row=3, column=3, sticky="w", pady=2)

        # Frames perdidos
        lbl_lost = tk.Label(self.avanzado_frame, text="Frames perdidos:")
        lbl_lost.grid(row=4, column=0, sticky="e", pady=2)

        self.max_lost_frames = tk.Spinbox(self.avanzado_frame, from_=0, to=100, width=10)
        self.max_lost_frames.delete(0, "end")
        self.max_lost_frames.insert(0, "3")
        self.max_lost_frames.grid(row=4, column=1, sticky="w", pady=2)

        # Base del servo y
        lbl_servo_y = tk.Label(self.avanzado_frame, text="Base del servo Y:")
        lbl_servo_y.grid(row=4, column=2, sticky="e", pady=2)

        self.servo_base_y = tk.Spinbox(self.avanzado_frame, from_=0, to=180, width=10)
        self.servo_base_y.delete(0, "end")
        self.servo_base_y.insert(0, "100")
        self.servo_base_y.grid(row=4, column=3, sticky="w", pady=2)

        # Frames para mantener el cuadrado
        lbl_keep = tk.Label(self.avanzado_frame, text="Frames de retención:")
        lbl_keep.grid(row=5, column=0, sticky="e", pady=2)

        self.keep_frames = tk.Spinbox(self.avanzado_frame, from_=0, to=100, width=10)
        self.keep_frames.delete(0, "end")
        self.keep_frames.insert(0, "10")
        self.keep_frames.grid(row=5, column=1, sticky="w", pady=2)

        # Modelo YOLO
        lbl_model = tk.Label(self.avanzado_frame, text="Modelo YOLO:")
        lbl_model.grid(row=5, column=2, sticky="e", pady=2)

        self.yolo_model = ttk.Combobox(self.avanzado_frame, values=["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x","yolov10n", "yolov10s", "yolov10m", "yolov10l", "yolov10x"], width=15)
        self.yolo_model.set("yolov10s")
        self.yolo_model.grid(row=5, column=3, sticky="w", pady=2)


        self.draw_boxes = tk.BooleanVar(value=True)
        tk.Checkbutton(self.avanzado_frame, text="Recuadros de personas", variable=self.draw_boxes).grid(row=6, column=1, columnspan=3, sticky="w", pady=2)

        self.vidriera_mode = tk.BooleanVar(value=False)
        tk.Checkbutton(self.avanzado_frame, text="Modo Vidriera", variable=self.vidriera_mode).grid(row=6, column=3, sticky="w", pady=2)

        # Botones de acción
        self.btn_start_nosave = tk.Button(scrollable_frame, text="Procesar sin guardar", command=self.start_tracking_no_save, width=20, height=2)
        self.btn_start_nosave.grid(row=16, column=0, columnspan=2, pady=10)

        self.btn_start = tk.Button(scrollable_frame, text="Procesar y guardar", command=self.start_tracking, width=20, height=2)
        self.btn_start.grid(row=16, column=2, columnspan=2, pady=10)

        self.btn_abrir_salida = tk.Button(scrollable_frame, text="Abrir Carpeta", command=self.abrir_carpeta_salida)
        self.btn_abrir_salida.grid(row=17, column=0, columnspan=4, pady=10)

        # Logo inferior
        image2 = Image.open(resource_path("untrefLogo.jpg")).resize((250, 100))
        self.logo_img2 = ImageTk.PhotoImage(image2)
        tk.Label(scrollable_frame, image=self.logo_img2).grid(row=18, column=0, columnspan=4, pady=10)

        self.on_mode_change()

    # Variable para trackear si está expandido
        self.avanzado_visible = True

    def toggle_avanzado(self):
        self.avanzado_visible = not self.avanzado_visible
        if self.avanzado_visible:
            self.avanzado_frame.grid()  # Mostrar
            self.btn_toggle.config(text="[-]")
        else:
            self.avanzado_frame.grid_remove()  # Ocultar
            self.btn_toggle.config(text="[+]")


    def on_mode_change(self):
        mode = self.input_mode.get()
        self.cam_index.config(state="normal" if mode == "camera" else "disabled")
        self.cam_index_sec.config(state="normal" if mode == "camera" else "disabled")
        self.combo_com.config(state="readonly" if mode == "camera" else "disabled")
        self.video_path.config(state="normal" if mode == "video" else "disabled")
        self.btn_browse.config(state="normal" if mode == "video" else "disabled")
        self.youtube_url.config(state="normal" if mode == "youtube" else "disabled")
        self.youtube_presets.config(state="readonly" if mode == "youtube" else "disabled")
        if mode != "youtube":
            self.youtube_url.delete(0, tk.END)

    def browse_video(self):
        path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")])
        if path:
            self.video_path.delete(0, tk.END)
            self.video_path.insert(0, path)

    def get_arduino_ports(self):
        ports = list_ports.comports()
        portsUsados =  [port.device for port in ports if "Arduino" in port.description or "CH340" in port.description or "ttyUSB" in port.device] or [port.device for port in ports]
        return portsUsados + [""]
    
    def _build_cmd(self, save_output=True):
        mode = self.input_mode.get()
        out_base = self.out_base.get().strip()
        fps = self.fps_entry.get().strip()
        resolution = self.resolution_combo.get().strip()

        if not out_base or not fps.isdigit():
            messagebox.showerror("Error", "Complete nombre y FPS válidos.")
            return None

        try:
            width, height = map(int, resolution.split('x'))
        except:
            messagebox.showerror("Error", "Resolución inválida.")
            return None

        output_folder = os.path.join(os.getcwd(), "output")
        os.makedirs(output_folder, exist_ok=True)

        confianza = str(int(self.conf_threshold.get())/100)

        cmd = [
            "--out-base", out_base,
            "--fps", fps,
            "--resolution", resolution,
            "--gainX", self.gainX_entry.get(),
            "--gainY", self.gainY_entry.get(),
            "--zoom", str(self.zoom_slider.get()),
            "--conf-threshold", confianza,
            "--max-lost-frames", self.max_lost_frames.get(),
            "--servo-base-x", self.servo_base_x.get(),
            "--servo-base-y", self.servo_base_y.get(),
            "--keep-frames", self.keep_frames.get(),
            "--yolo-model", self.yolo_model.get(),
        ]

        lista = [confianza, self.gainX_entry.get()]
        for elemento in lista:
            print(type(elemento))

        if not save_output:
            cmd.append("--no-save")

        if not self.draw_boxes.get():
            cmd.append("--no-boxes")

        if self.vidriera_mode.get():
            cmd.append("--vidriera-mode")

        port = self.combo_com.get().strip()

        if mode == "camera" and port:
            cmd += ["--camera", self.cam_index.get(),
                    "--camera-sec", self.cam_index_sec.get(),
                    "--camera-doble", "--com", port]
        elif mode == "camera":
            cmd += ["--camera", self.cam_index.get()]
            messagebox.showinfo("Camara", "No ha seleccionado un puerto COM.\nSe usará unicamente la cámara principal.")
        elif mode == "youtube":
            url = self.youtube_url.get().strip()
            if not url:
                messagebox.showerror("Error", "Ingrese una URL.")
                return None
            url_type = self.get_url_type(url)
            if url_type == "youtube":
                cmd += ["--youtube", url]
            elif url_type == "earthcam":
                cmd += ["--earthcam", url]
            else:
                messagebox.showerror("Error", "URL inválida o no compatible.\nSolo se admiten YouTube o EarthCam.")
                return None
        elif mode == "video":
            path = self.video_path.get().strip()
            if not path or not os.path.isfile(path):
                messagebox.showerror("Error", "Video inválido.")
                return None
            cmd += ["--video", path]

        return cmd


    def start_tracking(self):
        cmd = self._build_cmd(save_output=True)
        if cmd:
            try:
                detectarweb_main(cmd)  # Pasar lista completa de argumentos sin modificar
                messagebox.showinfo("Finalizado", "Procesamiento completado y guardado en /output.")
            except RuntimeError as e:
                messagebox.showerror("Error en video", str(e))
            except Exception as e:
                print(e)
                messagebox.showerror("Error durante el procesamiento", str(e))

    def start_tracking_no_save(self):
        cmd = self._build_cmd(save_output=False)
        if cmd:
            try:
                detectarweb_main(cmd)  # Pasar lista completa de argumentos sin modificar
                messagebox.showinfo("Ejecutando", "Procesamiento iniciado sin guardar salida.")
            except RuntimeError as e:
                messagebox.showerror("Error en video", str(e))
            except Exception as e:
                print(e)
                messagebox.showerror("Error durante el procesamiento", str(e))
                
    def analyze_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                df = pd.read_csv(path)
                df.plot()
                plt.show()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def abrir_carpeta_salida(self):
        output_path = os.path.join(os.getcwd(), "output")
        os.makedirs(output_path, exist_ok=True)  # Asegura que exista
        if platform.system() == "Windows":
            os.startfile(output_path)

# Ejecutar
root = tk.Tk()
root.title("Human Tracker")
root.state('zoomed')
app = TrackerGUI(master=root)
app.mainloop()
