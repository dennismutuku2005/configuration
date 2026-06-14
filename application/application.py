import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import time
import threading
from datetime import datetime


class SimpleTelnetClient:
    def __init__(self, host, port=23, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            return True
        except Exception:
            return False

    def send(self, data):
        if self.sock:
            self.sock.send(data.encode() + b'\n')

    def receive(self, timeout=2):
        if not self.sock:
            return ""
        self.sock.settimeout(timeout)
        try:
            data = b""
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'>' in chunk or b':' in chunk or b'#' in chunk:
                    time.sleep(0.1)
                    break
            return data.decode('utf-8', errors='ignore')
        except socket.timeout:
            return ""
        except Exception:
            return ""

    def login(self, username, password):
        if not self.connect():
            return False, "Connection failed"

        banner = self.receive(5)

        if "Login:" in banner or "login:" in banner:
            self.send(username)
        else:
            time.sleep(1)
            self.send(username)

        time.sleep(1)
        self.receive(3)
        self.send(password)
        time.sleep(2)
        prompt = self.receive(3)

        if ">" not in prompt and "#" not in prompt:
            self.sock.close()
            return False, "Login failed - invalid credentials"

        return True, "Login successful"

    def remove_security(self, version, ssid_index):
        results = []

        if version == "5":
            # Only modify the specific SSID index selected
            commands = [
                f"set ssid index {ssid_index} security None"
            ]
        else:
            # Version 6 - only modify the specific wlaninst selected
            commands = [
                f"set wlan basic laninst 1 wlaninst {ssid_index} beaconType None",
                f"set wlan basic laninst 1 wlaninst {ssid_index} basicauthenticationmode None"
            ]

        for cmd in commands:
            self.send(cmd)
            time.sleep(1)
            output = self.receive(2)
            if output and ("ERROR" in output or "ErrCode" in output):
                results.append(("Failed", cmd))
            else:
                results.append(("Success", cmd))

        return results

    def save_configuration(self):
        self.send("save data")
        time.sleep(2)
        self.receive(3)
        return True

    def logout(self):
        if self.sock:
            try:
                self.send("exit")
                self.send("exit")
                time.sleep(1)
                self.sock.close()
            except Exception:
                pass


class RouterApp:
    ROUTER_IP = "192.168.100.1"
    PORT = 23
    USERNAME = "root"
    PASSWORD = "Nuuo0678."  # Default password for both versions

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WiFi Security Manager")
        self.root.geometry("720x580")
        self.root.minsize(640, 500)
        self.root.configure(bg="#ffffff")

        self.version = tk.StringVar(value="5")
        self.ssid_vars = {}
        self.client = None

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure(".", background="#ffffff", foreground="#1a1a1a", font=("Segoe UI", 10))
        style.configure("TFrame", background="#ffffff")
        style.configure("TLabelframe", background="#ffffff", bordercolor="#e0e0e0", relief="solid")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#666666",
                        font=("Segoe UI", 9))

        style.configure("TRadiobutton", background="#ffffff", foreground="#1a1a1a",
                        font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#ffffff", foreground="#1a1a1a",
                        font=("Segoe UI", 10))

        style.configure("TButton", background="#f5f5f5", foreground="#1a1a1a",
                        bordercolor="#d0d0d0", relief="solid", padding=(10, 6),
                        font=("Segoe UI", 10))
        style.map("TButton",
                  background=[("active", "#ebebeb"), ("disabled", "#f9f9f9")],
                  foreground=[("disabled", "#aaaaaa")])

        style.configure("Primary.TButton", background="#1a1a1a", foreground="#ffffff",
                        bordercolor="#1a1a1a", font=("Segoe UI", 10, "bold"), padding=(10, 7))
        style.map("Primary.TButton",
                  background=[("active", "#333333"), ("disabled", "#cccccc")],
                  foreground=[("disabled", "#888888")])

    def _build_ui(self):
        root_pad = ttk.Frame(self.root, padding="20 16 20 16")
        root_pad.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = ttk.Frame(root_pad)
        hdr.pack(fill=tk.X, pady=(0, 14))

        ttk.Label(hdr, text="WiFi Security Manager",
                  font=("Segoe UI", 15, "bold"), foreground="#1a1a1a").pack(side=tk.LEFT)

        self.status_label = ttk.Label(hdr, text="  Disconnected",
                                      font=("Segoe UI", 9), foreground="#999999")
        self.status_label.pack(side=tk.RIGHT, pady=(4, 0))

        ttk.Separator(root_pad, orient="horizontal").pack(fill=tk.X, pady=(0, 14))

        # Warning
        warn_frame = tk.Frame(root_pad, bg="#fff8e6", relief="flat", bd=0)
        warn_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(warn_frame,
                 text="⚠ Warning: Selected SSIDs will have their passwords removed and become open networks.",
                 bg="#fff8e6", fg="#7a5800", font=("Segoe UI", 9),
                 anchor="w", pady=7, padx=10, wraplength=640, justify="left").pack(fill=tk.X)

        # Two-column row: version + connection info
        row = ttk.Frame(root_pad)
        row.pack(fill=tk.X, pady=(0, 14))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        version_frame = ttk.LabelFrame(row, text="Router model", padding="10 8")
        version_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ttk.Radiobutton(version_frame, text="HG8145V5 (version 5)",
                        variable=self.version, value="5").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(version_frame, text="HG8145V6 (version 6)",
                        variable=self.version, value="6").pack(anchor=tk.W, pady=2)

        conn_frame = ttk.LabelFrame(row, text="Target", padding="10 8")
        conn_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ttk.Label(conn_frame, text="192.168.100.1 : 23",
                  font=("Segoe UI", 10), foreground="#1a1a1a").pack(anchor=tk.W)
        ttk.Label(conn_frame, text="Telnet / root",
                  font=("Segoe UI", 9), foreground="#999999").pack(anchor=tk.W, pady=(2, 0))

        # SSID selection
        ssid_frame = ttk.LabelFrame(root_pad, text="Select SSIDs to modify", padding="10 8")
        ssid_frame.pack(fill=tk.X, pady=(0, 14))

        # Info about bands
        info_frame = ttk.Frame(ssid_frame)
        info_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(info_frame, text="Note: Each SSID index is modified independently.",
                  font=("Segoe UI", 8), foreground="#666666").pack(anchor=tk.W)

        grid = ttk.Frame(ssid_frame)
        grid.pack(fill=tk.X, pady=(0, 8))

        for i in range(1, 9):
            var = tk.BooleanVar()
            self.ssid_vars[i] = var
            cb = ttk.Checkbutton(grid, text=f"SSID {i}", variable=var)
            cb.grid(row=(i - 1) // 4, column=(i - 1) % 4, padx=12, pady=4, sticky=tk.W)

        btn_row = ttk.Frame(ssid_frame)
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row, text="Select all", command=self._select_all).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="Clear", command=self._select_none).pack(side=tk.LEFT)

        # Action row
        action_row = ttk.Frame(root_pad)
        action_row.pack(fill=tk.X, pady=(0, 14))

        self.remove_btn = ttk.Button(action_row, text="Remove passwords",
                                     style="Primary.TButton", command=self._run)
        self.remove_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(action_row, text="Clear log", command=self._clear_log).pack(side=tk.LEFT)

        # Log
        log_frame = ttk.LabelFrame(root_pad, text="Log", padding="6 4")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log = scrolledtext.ScrolledText(
            log_frame, height=8, wrap=tk.WORD,
            font=("Consolas", 9), relief="flat", bd=0,
            background="#fafafa", foreground="#333333"
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.tag_config("ok", foreground="#1a7a3f")
        self.log.tag_config("err", foreground="#c0392b")
        self.log.tag_config("dim", foreground="#999999")
        self.log.tag_config("warn", foreground="#b07d00")

    # ------------------------------------------------------------------ helpers

    def _log(self, msg, tag=None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert(tk.END, f"  {ts}  {msg}\n", tag)
        self.log.see(tk.END)
        self.root.update_idletasks()

    def _clear_log(self):
        self.log.delete("1.0", tk.END)

    def _select_all(self):
        for v in self.ssid_vars.values():
            v.set(True)

    def _select_none(self):
        for v in self.ssid_vars.values():
            v.set(False)

    def _set_status(self, text, color="#999999"):
        self.status_label.config(text=f"  {text}", foreground=color)

    # ------------------------------------------------------------------ main action

    def _run(self):
        selected = [i for i in range(1, 9) if self.ssid_vars[i].get()]

        if not selected:
            messagebox.showwarning("Nothing selected", "Select at least one SSID.")
            return

        def worker():
            self.remove_btn.config(state=tk.DISABLED, text="Working...")
            self._set_status("Connecting...", "#b07d00")

            # Connect
            self._log(f"Connecting to {self.ROUTER_IP}:{self.PORT}...", "dim")
            self.client = SimpleTelnetClient(self.ROUTER_IP, self.PORT, timeout=10)
            ok, msg = self.client.login(self.USERNAME, self.PASSWORD)

            if not ok:
                self._log(f"Connection failed: {msg}", "err")
                self._set_status("Disconnected", "#c0392b")
                self.remove_btn.config(state=tk.NORMAL, text="Remove passwords")
                return

            self._log("Authenticated", "ok")
            self._set_status("Connected", "#1a7a3f")

            self.client.send("su")
            time.sleep(2)
            self.client.receive(2)
            self._log("Super user mode active", "dim")

            # Process SSIDs - each selected index independently
            version = self.version.get()
            self._log(f"Router version: {version}  /  Selected SSIDs: {', '.join(str(s) for s in selected)}", "dim")

            success_count = 0
            for ssid in selected:
                self._log(f"Processing SSID {ssid}...", "dim")
                results = self.client.remove_security(version, ssid)
                all_ok = all(status == "Success" for status, _ in results)
                if all_ok:
                    self._log(f"✓ SSID {ssid} — password removed", "ok")
                    success_count += 1
                else:
                    self._log(f"✗ SSID {ssid} — one or more commands failed", "err")
                    for status, cmd in results:
                        if status == "Failed":
                            self._log(f"  failed: {cmd}", "err")
                time.sleep(0.5)

            if success_count:
                self._log("Saving configuration...", "dim")
                self.client.save_configuration()
                self._log(f"✓ Done. {success_count} SSID(s) are now open.", "warn")
            else:
                self._log("✗ No SSIDs were configured successfully.", "err")

            self.client.logout()
            self._set_status("Disconnected", "#999999")
            self.remove_btn.config(state=tk.NORMAL, text="Remove passwords")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ lifecycle

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    RouterApp().run()