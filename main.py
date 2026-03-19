import os
import sys
import traceback
import json

# --- CAPTURA DE ERRORES AL INICIO (para debug del .exe) ---
_log_path = None
if getattr(sys, 'frozen', False):
    _log_path = os.path.join(os.path.dirname(sys.executable), 'error_log.txt')
    _log_file = open(_log_path, 'w', encoding='utf-8')
    sys.stdout = _log_file
    sys.stderr = _log_file

try:
    import re
    import requests
    import yt_dlp
    import threading
    import time
    import webbrowser
    import winsound
    import paramiko
    import customtkinter as ctk
    from PIL import Image, ImageTk
    from spotify_scraper import SpotifyClient
except Exception:
    if _log_path:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write("=== ERROR AL IMPORTAR LIBRERIAS ===\n")
            traceback.print_exc(file=f)
    raise


# --- FIX PARA INTERFAZ EN WINDOWS (TCL/TK) ---
def apply_tcl_fix():
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
            tcl_path = os.path.join(base, '_internal', '_tcl_data')
            tk_path  = os.path.join(base, '_internal', '_tk_data')
            if not os.path.exists(tcl_path):
                tcl_path = os.path.join(base, '_tcl_data')
                tk_path  = os.path.join(base, '_tk_data')
            os.environ['TCL_LIBRARY'] = tcl_path
            os.environ['TK_LIBRARY']  = tk_path
        else:
            base = sys.base_prefix
            os.environ['TCL_LIBRARY'] = os.path.join(base, 'tcl', 'tcl8.6')
            os.environ['TK_LIBRARY']  = os.path.join(base, 'tcl', 'tk8.6')
    except Exception:
        pass


apply_tcl_fix()

# --- ARCHIVO DE CONFIGURACION SFTP (persistente junto al .exe) ---
CONFIG_FILE = os.path.join(
    os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd(),
    'sftp_config.json'
)


def load_sftp_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"servers": []}


def save_sftp_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando config SFTP: {e}")


# ─────────────────────────────────────────────
# VENTANA: CONFIGURACION DE SERVIDORES SFTP
# ─────────────────────────────────────────────
class SFTPConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configuración SFTP")
        self.geometry("620x560")
        self.resizable(False, False)
        self.grab_set()

        self.config_data    = load_sftp_config()
        self.selected_index = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)

        # ── Panel izquierdo: lista ──
        left = ctk.CTkFrame(self, width=185)
        left.grid(row=0, column=0, padx=(15, 7), pady=15, sticky="nsew")
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Servidores guardados",
                     font=("Segoe UI", 12, "bold")).pack(pady=(12, 5))

        self.server_list = ctk.CTkScrollableFrame(left, width=165, height=340)
        self.server_list.pack(padx=8, pady=5, fill="both", expand=True)

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(pady=8)
        ctk.CTkButton(btn_row, text="＋ Nuevo", width=78, height=30,
                      fg_color="#1DB954", hover_color="#179443",
                      command=self.new_server).grid(row=0, column=0, padx=3)
        ctk.CTkButton(btn_row, text="🗑 Borrar", width=78, height=30,
                      fg_color="#b94040", hover_color="#8f2f2f",
                      command=self.delete_server).grid(row=0, column=1, padx=3)

        # ── Panel derecho: formulario ──
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, padx=(7, 15), pady=15, sticky="nsew")

        ctk.CTkLabel(right, text="Datos del servidor",
                     font=("Segoe UI", 13, "bold")).pack(pady=(15, 10))

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.pack(padx=18, fill="x")
        form.grid_columnconfigure(1, weight=1)

        def field(label, row, show=None):
            ctk.CTkLabel(form, text=label, anchor="w", width=90).grid(
                row=row, column=0, sticky="w", pady=5)
            e = ctk.CTkEntry(form, show=show)
            e.grid(row=row, column=1, padx=(10, 0), pady=5, sticky="ew")
            return e

        self.f_name  = field("Nombre",      0)
        self.f_host  = field("Host / IP",   1)
        self.f_port  = field("Puerto",      2)
        self.f_user  = field("Usuario",     3)
        self.f_pass  = field("Contraseña",  4, show="●")
        self.f_rpath = field("Ruta remota", 5)

        self.f_port.insert(0, "22")
        self.f_rpath.insert(0, "/")

        ctk.CTkButton(right, text="💾  Guardar servidor",
                      fg_color="#1DB954", hover_color="#179443",
                      font=("Segoe UI", 13, "bold"), height=42,
                      command=self.save_server).pack(pady=15, padx=18, fill="x")

        self.status_lbl = ctk.CTkLabel(right, text="Seleccioná un servidor o creá uno nuevo",
                                       font=("Segoe UI", 11), text_color="#666")
        self.status_lbl.pack()

        self.refresh_list()

    def refresh_list(self):
        for w in self.server_list.winfo_children():
            w.destroy()
        for i, srv in enumerate(self.config_data["servers"]):
            ctk.CTkButton(
                self.server_list,
                text=srv.get("name", f"Servidor {i+1}"),
                fg_color="#2a2a2a", hover_color="#383838",
                anchor="w", height=34,
                command=lambda idx=i: self.load_server(idx)
            ).pack(fill="x", pady=2)

    def load_server(self, index):
        self.selected_index = index
        srv = self.config_data["servers"][index]
        for entry, key, default in [
            (self.f_name,  "name",        ""),
            (self.f_host,  "host",        ""),
            (self.f_port,  "port",        "22"),
            (self.f_user,  "user",        ""),
            (self.f_pass,  "password",    ""),
            (self.f_rpath, "remote_path", "/"),
        ]:
            entry.delete(0, "end")
            entry.insert(0, srv.get(key, default))
        self.status_lbl.configure(text=f"Editando: {srv.get('name','')}", text_color="#aaa")

    def new_server(self):
        self.selected_index = None
        for entry in [self.f_name, self.f_host, self.f_user, self.f_pass]:
            entry.delete(0, "end")
        self.f_port.delete(0, "end");  self.f_port.insert(0, "22")
        self.f_rpath.delete(0, "end"); self.f_rpath.insert(0, "/")
        self.status_lbl.configure(text="Nuevo servidor — completá los datos", text_color="#aaa")

    def save_server(self):
        srv = {
            "name":        self.f_name.get().strip()  or "Sin nombre",
            "host":        self.f_host.get().strip(),
            "port":        self.f_port.get().strip()  or "22",
            "user":        self.f_user.get().strip(),
            "password":    self.f_pass.get(),
            "remote_path": self.f_rpath.get().strip() or "/",
        }
        if not srv["host"] or not srv["user"]:
            self.status_lbl.configure(text="⚠ Host y Usuario son obligatorios",
                                      text_color="#e05050")
            return
        if self.selected_index is not None:
            self.config_data["servers"][self.selected_index] = srv
        else:
            self.config_data["servers"].append(srv)
            self.selected_index = len(self.config_data["servers"]) - 1

        save_sftp_config(self.config_data)
        self.refresh_list()
        self.status_lbl.configure(text="✅ Guardado correctamente", text_color="#1DB954")

    def delete_server(self):
        if self.selected_index is None:
            self.status_lbl.configure(text="⚠ Seleccioná un servidor primero",
                                      text_color="#e05050")
            return
        name = self.config_data["servers"][self.selected_index].get("name", "")
        self.config_data["servers"].pop(self.selected_index)
        self.selected_index = None
        save_sftp_config(self.config_data)
        self.new_server()
        self.refresh_list()
        self.status_lbl.configure(text=f"'{name}' eliminado", text_color="#aaa")


# ─────────────────────────────────────────────
# VENTANA: SUBIDA AL SFTP
# ─────────────────────────────────────────────
class SFTPUploadWindow(ctk.CTkToplevel):
    def __init__(self, parent, base_dir, log_callback):
        super().__init__(parent)
        self.title("Subir música al SFTP")
        self.geometry("520x430")
        self.resizable(False, False)
        self.grab_set()

        self.base_dir     = base_dir
        self.log_callback = log_callback
        self.config_data  = load_sftp_config()

        ctk.CTkLabel(self, text="☁  Subir al SFTP",
                     font=("Segoe UI", 20, "bold"), text_color="#1DB954").pack(pady=(20, 5))

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=20, fill="x", pady=8)

        ctk.CTkLabel(frame, text="Servidor destino:", anchor="w").pack(fill="x")

        names = [s.get("name", f"Servidor {i+1}") for i, s in
                 enumerate(self.config_data.get("servers", []))]
        if not names:
            names = ["(sin servidores configurados)"]

        self.server_var  = ctk.StringVar(value=names[0])
        self.server_menu = ctk.CTkOptionMenu(frame, values=names, variable=self.server_var,
                                             fg_color="#282828", button_color="#1DB954",
                                             button_hover_color="#179443", height=38)
        self.server_menu.pack(fill="x", pady=5)

        self.all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="Subir a TODOS los servidores a la vez",
                        variable=self.all_var,
                        checkbox_width=20, checkbox_height=20,
                        fg_color="#1DB954", hover_color="#179443",
                        font=("Segoe UI", 12)).pack(anchor="w", pady=6)

        self.textbox = ctk.CTkTextbox(self, height=155, font=("Consolas", 11),
                                      border_width=1, border_color="#333")
        self.textbox.pack(padx=20, pady=8, fill="x")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=8)

        self.upload_btn = ctk.CTkButton(btn_row, text="🚀  Iniciar subida",
                                        fg_color="#1DB954", hover_color="#179443",
                                        font=("Segoe UI", 14, "bold"), width=200, height=42,
                                        command=self.start_upload)
        self.upload_btn.grid(row=0, column=0, padx=10)

        ctk.CTkButton(btn_row, text="Cerrar", fg_color="#333", hover_color="#444",
                      width=100, height=42, command=self.destroy).grid(row=0, column=1, padx=10)

    def log(self, msg):
        self.textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.textbox.see("end")
        try:
            self.log_callback(msg)
        except Exception:
            pass

    def start_upload(self):
        servers = self.config_data.get("servers", [])
        if not servers:
            self.log("⚠ No hay servidores configurados. Usá ⚙ para agregar uno.")
            return

        targets = servers if self.all_var.get() else \
                  [s for s in servers if s.get("name") == self.server_var.get()]

        if not targets:
            self.log("⚠ No se encontró el servidor seleccionado.")
            return

        self.upload_btn.configure(state="disabled")
        threading.Thread(target=self._upload_worker, args=(targets,), daemon=True).start()

    def _upload_worker(self, targets):
        for srv in targets:
            self.log(f"── Conectando a {srv['name']} ({srv['host']}:{srv.get('port',22)}) ──")
            try:
                transport = paramiko.Transport((srv["host"], int(srv.get("port", 22))))
                transport.connect(username=srv["user"], password=srv["password"])
                sftp = paramiko.SFTPClient.from_transport(transport)

                remote_base = srv.get("remote_path", "/").rstrip("/")
                uploaded = errors = 0

                for artist_folder in os.listdir(self.base_dir):
                    local_artist = os.path.join(self.base_dir, artist_folder)
                    if not os.path.isdir(local_artist):
                        continue

                    remote_artist = f"{remote_base}/{artist_folder}"
                    try:
                        sftp.stat(remote_artist)
                    except FileNotFoundError:
                        sftp.mkdir(remote_artist)

                    for fname in os.listdir(local_artist):
                        if not fname.lower().endswith(('.mp3', '.m4a')):
                            continue
                        local_file  = os.path.join(local_artist, fname)
                        remote_file = f"{remote_artist}/{fname}"
                        try:
                            sftp.put(local_file, remote_file)
                            self.log(f"   ✅ {artist_folder}/{fname}")
                            uploaded += 1
                        except Exception as ef:
                            self.log(f"   ❌ {fname}: {ef}")
                            errors += 1

                sftp.close()
                transport.close()
                self.log(f"── {srv['name']}: {uploaded} subidos, {errors} errores ──")

            except Exception as es:
                self.log(f"❌ Error en {srv['name']}: {es}")

        self.upload_btn.configure(state="normal")
        self.log("=== Proceso terminado ===")


# ─────────────────────────────────────────────
# VENTANA PRINCIPAL
# ─────────────────────────────────────────────
class RxScrapperGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("RxScrapper Pro")
        self.geometry("750x680")
        self._set_icon()
        self.grid_columnconfigure(0, weight=1)

        self.brand_color = "#1DB954"

        # Encabezado
        ctk.CTkLabel(self, text="Spotify RxScrapper", font=("Segoe UI", 34, "bold"),
                     text_color=self.brand_color).pack(pady=(30, 5))
        ctk.CTkLabel(self, text="Descargador Universal (Track, Artista, Playlist)",
                     font=("Segoe UI", 13)).pack(pady=(0, 20))

        # Fila de entrada
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(pady=10, padx=30, fill="x")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(self.input_frame,
                                      placeholder_text="Pega el enlace de Spotify aquí...",
                                      height=45)
        self.url_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.format_option = ctk.CTkOptionMenu(
            self.input_frame, values=["m4a (Rápido)", "mp3 (Universal)"],
            width=140, height=45, fg_color="#282828",
            button_color=self.brand_color, button_hover_color="#179443")
        self.format_option.grid(row=0, column=1)
        self.format_option.set("m4a (Rápido)")

        # Checkbox SFTP automático
        sftp_row = ctk.CTkFrame(self, fg_color="transparent")
        sftp_row.pack(pady=(5, 0))
        self.auto_sftp_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sftp_row,
                        text="Subir al SFTP automáticamente al terminar la descarga",
                        variable=self.auto_sftp_var,
                        checkbox_width=20, checkbox_height=20,
                        fg_color=self.brand_color, hover_color="#179443",
                        font=("Segoe UI", 12)).pack()

        # Botones principales
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=18)

        self.download_btn = ctk.CTkButton(
            self.btn_frame, text="INICIAR DESCARGA", command=self.start_thread,
            fg_color=self.brand_color, hover_color="#179443",
            font=("Segoe UI", 15, "bold"), width=220, height=52)
        self.download_btn.grid(row=0, column=0, padx=7)

        ctk.CTkButton(self.btn_frame, text="☁ SFTP", command=self.open_sftp_upload,
                      fg_color="#2a6496", hover_color="#1f4d73",
                      font=("Segoe UI", 14, "bold"), width=110, height=52
                      ).grid(row=0, column=1, padx=7)

        ctk.CTkButton(self.btn_frame, text="⚙", command=self.open_sftp_config,
                      fg_color="#333", hover_color="#444",
                      width=52, height=52, font=("Segoe UI", 18)
                      ).grid(row=0, column=2, padx=4)

        ctk.CTkButton(self.btn_frame, text="📁", command=self.open_folder,
                      fg_color="#333", hover_color="#444",
                      width=52, height=52, font=("Segoe UI", 18)
                      ).grid(row=0, column=3, padx=4)

        # Log
        self.textbox = ctk.CTkTextbox(self, width=690, height=235, font=("Consolas", 12),
                                      border_width=1, border_color="#333333")
        self.textbox.pack(pady=10, padx=30)

        self.status_var = ctk.StringVar(value="Sistema listo")
        ctk.CTkLabel(self, textvariable=self.status_var,
                     font=("Segoe UI", 11), text_color="#777777").pack(pady=8)

        self.client   = None
        self.base_dir = "Descargas_RxScrapper"

    def log(self, msg):
        self.textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.textbox.see("end")

    def open_folder(self):
        os.makedirs(self.base_dir, exist_ok=True)
        webbrowser.open(os.path.abspath(self.base_dir))

    def open_sftp_config(self):
        SFTPConfigWindow(self)

    def open_sftp_upload(self):
        os.makedirs(self.base_dir, exist_ok=True)
        SFTPUploadWindow(self, self.base_dir, self.log)

    def start_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        fmt = "mp3" if "mp3" in self.format_option.get() else "m4a"
        self.download_btn.configure(state="disabled")
        self.textbox.delete("1.0", "end")
        threading.Thread(target=self.worker_logic, args=(url, fmt), daemon=True).start()

    def worker_logic(self, url, fmt):
        self.status_var.set("Analizando...")

        if getattr(sys, 'frozen', False):
            ffmpeg_bin = os.path.join(sys._MEIPASS, "ffmpeg", "bin", "ffmpeg.exe")
        else:
            ffmpeg_bin = os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe")

        if not self.client:
            self.client = SpotifyClient()

        try:
            if "track" in url:
                match = re.search(r'track/([a-zA-Z0-9]+)', url)
                ids = [match.group(1)] if match else []
            else:
                res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                ids = list(set(re.findall(r'spotify:track:([a-zA-Z0-9]+)', res.text)))
                if not ids:
                    ids = list(set(re.findall(r'/track/([a-zA-Z0-9]+)', res.text)))

            if not ids:
                self.log("No se encontró contenido.")
            else:
                self.log(f"Detectadas {len(ids)} canciones.")
                for i, t_id in enumerate(ids):
                    self.status_var.set(f"Descargando {i + 1}/{len(ids)}...")
                    t_url = f"https://open.spotify.com/track/{t_id}"
                    try:
                        info = self.client.get_track_info(t_url)
                        art = re.sub(r'[<>:"/\\|?*]', '',
                                     info['artists'][0]['name'] if info.get('artists') else 'Artista')
                        nom = re.sub(r'[<>:"/\\|?*]', '', info.get('name', t_id))
                        path = os.path.join(self.base_dir, art)
                        os.makedirs(path, exist_ok=True)
                        self.log(f"-> {art} - {nom} ({fmt.upper()})")
                        try:
                            self.client.download_cover(t_url, path=path)
                        except Exception:
                            pass

                        ydl_opts = {
                            'format': 'bestaudio/best',
                            'outtmpl': f'{path}/{nom}.%(ext)s',
                            'quiet': True,
                            'default_search': 'ytsearch',
                            'nocheckcertificate': True,
                            'ffmpeg_location': ffmpeg_bin,
                        }
                        if fmt == "mp3":
                            ydl_opts['postprocessors'] = [{
                                'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3',
                                'preferredquality': '192'
                            }]
                        else:
                            ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                            ydl_opts['merge_output_format'] = 'm4a'

                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([f"ytsearch1:{art} {nom} audio"])
                            self.log(f"   [OK] Finalizado.")
                    except Exception as e_track:
                        self.log(f"   [!] Error en pista: {str(e_track)}")

                self.status_var.set("¡Descarga lista!")
                winsound.MessageBeep()

                # ── SFTP AUTOMATICO ──
                if self.auto_sftp_var.get():
                    self.log("── Iniciando subida automática al SFTP ──")
                    cfg = load_sftp_config()
                    servers = cfg.get("servers", [])
                    if servers:
                        win = SFTPUploadWindow(self, self.base_dir, self.log)
                        win._upload_worker(servers)
                    else:
                        self.log("⚠ SFTP automático activado pero no hay servidores configurados.")
                        self.log("   Usá el botón ⚙ para agregar un servidor SFTP.")

        except Exception as e:
            self.log(f"Error Crítico: {str(e)}")

        self.download_btn.configure(state="normal")

    def _set_icon(self):
        try:
            if getattr(sys, 'frozen', False):
                base = sys._MEIPASS
            else:
                base = os.getcwd()

            ico_path = os.path.join(base, 'img', 'icono.ico')

            # Si no existe el .ico lo generamos desde el .png al vuelo
            if not os.path.exists(ico_path):
                png_path = os.path.join(base, 'img', 'icono.png')
                if os.path.exists(png_path):
                    Image.open(png_path).save(
                        ico_path, format='ICO',
                        sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]
                    )

            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
                # CustomTkinter puede pisar el ícono durante su init,
                # lo reaplicamos 200ms después para asegurar que quede.
                self.after(200, lambda: self.iconbitmap(ico_path))

        except Exception:
            pass


if __name__ == "__main__":
    try:
        ctk.set_appearance_mode("Dark")
        app = RxScrapperGUI()
        app.mainloop()
    except Exception:
        if _log_path:
            with open(_log_path, 'a', encoding='utf-8') as f:
                f.write("=== ERROR AL INICIAR LA APP ===\n")
                traceback.print_exc(file=f)
        raise