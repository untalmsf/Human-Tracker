import os, subprocess, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from serial.tools import list_ports
import sys

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

class TrackerGUI(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

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


        tk.Label(scrollable_frame, text="", padx=50, pady=50).grid(row=0, column=0, sticky="w")
        image = Image.open(resource_path("logo.png")).resize((300, 300))
        self.logo_img = ImageTk.PhotoImage(image)
        tk.Label(scrollable_frame, image=self.logo_img).grid(row=1, column=0, columnspan=4, pady=10)

        self.input_mode = tk.StringVar(value="camera")
        tk.Radiobutton(scrollable_frame, text="Camara", variable=self.input_mode, value="camera", command=self.on_mode_change).grid(row=2, column=0, sticky="w")
        tk.Radiobutton(scrollable_frame, text="Camara Rotativa", variable=self.input_mode, value="CamaraRot", command=self.on_mode_change).grid(row=3, column=0, sticky="w")
        tk.Radiobutton(scrollable_frame, text="Camara publica", variable=self.input_mode, value="youtube", command=self.on_mode_change).grid(row=4, column=0, sticky="w")
        tk.Radiobutton(scrollable_frame, text="Video", variable=self.input_mode, value="video", command=self.on_mode_change).grid(row=5, column=0, sticky="w")

        tk.Label(scrollable_frame, text="Camara:").grid(row=2, column=1, sticky="e")
        self.cam_index = tk.Spinbox(scrollable_frame, from_=0, to=2, width=5)
        self.cam_index.grid(row=2, column=2, sticky="w")

        self.label_com = tk.Label(scrollable_frame, text="Puerto COM:")
        self.label_com.grid(row=3, column=1, sticky="e")
        self.combo_com = ttk.Combobox(scrollable_frame, values=self.get_arduino_ports(), width=15)
        self.combo_com.grid(row=3, column=2, sticky="w")

        self.youtube_options = {
            "Personalizado": "",
            "Times Square": "https://www.youtube.com/watch?v=rnXIjl_Rzy4",
            "Pinamar": "https://www.youtube.com/watch?v=VUODMJsRM9E",
            "Deadwood": "https://www.youtube.com/watch?v=IkxxNB-3HEw",
            "Mundo": "https://www.youtube.com/watch?v=z7SiAaN4ogw"
        }

        self.youtube_presets = ttk.Combobox(scrollable_frame, state="readonly", width=25)
        self.youtube_presets['values'] = list(self.youtube_options.keys())
        self.youtube_presets.set("Personalizado")
        self.youtube_presets.grid(row=4, column=1, sticky="w")
        self.youtube_presets.bind("<<ComboboxSelected>>", self.on_preset_change)

        tk.Label(scrollable_frame, text="URL:").grid(row=4, column=2, sticky="e")
        self.youtube_url = tk.Entry(scrollable_frame, width=30, state="disabled")
        self.youtube_url.grid(row=4, column=3, sticky="w")

        self.video_path = tk.Entry(scrollable_frame, width=30, state="disabled")
        self.video_path.grid(row=5, column=1, columnspan=2, sticky="w")
        self.btn_browse = tk.Button(scrollable_frame, text="Buscar...", command=self.browse_video, state="disabled")
        self.btn_browse.grid(row=5, column=3)

        tk.Label(scrollable_frame, text="Nombre del video:").grid(row=6, column=0, sticky="e")
        self.out_base = tk.Entry(scrollable_frame, width=20)
        self.out_base.insert(0, "output")
        self.out_base.grid(row=6, column=1, columnspan=2, sticky="w")

        tk.Label(scrollable_frame, text="FPS:").grid(row=7, column=0, sticky="e")
        self.fps_entry = tk.Entry(scrollable_frame, width=10)
        self.fps_entry.insert(0, "30")
        self.fps_entry.grid(row=7, column=1, sticky="w")

        tk.Label(scrollable_frame, text="Resolución:").grid(row=8, column=0, sticky="e")
        self.resolution_combo = ttk.Combobox(scrollable_frame, values=["640x480", "1280x720", "1920x1080"], width=15)
        self.resolution_combo.set("640x480")
        self.resolution_combo.grid(row=8, column=1, sticky="w")

        self.draw_boxes = tk.BooleanVar(value=True)
        tk.Checkbutton(scrollable_frame, text="Bounding boxes", variable=self.draw_boxes).grid(row=9, column=0, columnspan=3, sticky="w")

        self.btn_start = tk.Button(scrollable_frame, text="Procesar y guardar", command=self.start_tracking)
        self.btn_start.grid(row=10, column=2, pady=10)

        self.btn_start_nosave = tk.Button(scrollable_frame, text="Procesar sin guardar", command=self.start_tracking_no_save)
        self.btn_start_nosave.grid(row=10, column=1, pady=10)

        self.btn_analyze = tk.Button(scrollable_frame, text="Analizar CSV", command=self.analyze_csv)
        self.btn_analyze.grid(row=11, column=0, columnspan=4, pady=10)

        image2 = Image.open(resource_path("untrefLogo.jpg")).resize((250, 100))
        self.logo_img2 = ImageTk.PhotoImage(image2)
        tk.Label(scrollable_frame, image=self.logo_img2).grid(row=13, column=0, columnspan=4, pady=10)

        self.on_mode_change()

    def on_mode_change(self):
        mode = self.input_mode.get()
        self.cam_index.config(state="normal" if mode in ["camera", "CamaraRot"] else "disabled")
        self.combo_com.config(state="readonly" if mode == "CamaraRot" else "disabled")
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
        return [port.device for port in ports if "Arduino" in port.description or "CH340" in port.description or "ttyUSB" in port.device] or [port.device for port in ports]

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

        output_folder = os.path.join(os.getcwd(), "outputs")
        os.makedirs(output_folder, exist_ok=True)
        out_base_path = os.path.join(output_folder, out_base)

        script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        if ("Human Tracker.exe" in sys.executable) :
            script =  os.path.join(script_dir, "detectarweb.exe") # usamos el .exe directamente
            cmd =  [script, "--out-base", out_base, "--fps", fps, "--resolution", resolution] 
        else:
            script = os.path.join(script_dir, "detectarweb.py") 
            cmd = ["python", script, "--out-base", out_base, "--fps", fps, "--resolution", resolution]

        if not save_output:
            cmd.append("--no-save")

        if not self.draw_boxes.get():
            cmd.append("--no-boxes")

        if mode == "camera":
            cmd += ["--camera", self.cam_index.get()]
        elif mode == "CamaraRot":
            port = self.combo_com.get().strip()
            if not port:
                messagebox.showerror("Error", "Seleccione puerto COM.")
                return None
            cmd += ["--camera", self.cam_index.get(), "--modo-rotativa", "--com", port]
        elif mode == "youtube":
            yt = self.youtube_url.get().strip()
            if "youtube.com" not in yt and "youtu.be" not in yt:
                messagebox.showerror("Error", "URL de YouTube inválida.")
                return None
            cmd += ["--youtube", yt]
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
            proc = subprocess.Popen(cmd)
            proc.wait()
            messagebox.showinfo("Finalizado", "Procesamiento completado y guardado en /outputs.")

    def start_tracking_no_save(self):
        cmd = self._build_cmd(save_output=False)
        if cmd:
            subprocess.Popen(cmd)
            messagebox.showinfo("Ejecutando", "Procesamiento iniciado sin guardar salida.")

    def analyze_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                df = pd.read_csv(path)
                df.plot()
                plt.show()
            except Exception as e:
                messagebox.showerror("Error", str(e))

# Ejecutar
root = tk.Tk()
root.title("Human Tracker")
root.state('zoomed')
app = TrackerGUI(master=root)
app.mainloop()
