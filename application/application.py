import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import time
import threading
from datetime import datetime
import json
import os
import re
import webbrowser
import urllib.request
import urllib.error

# Import the machine ID module
from machine_id import get_machine_id, get_machine_info, verify_machine_id


# App Version Constant
APP_VERSION = "2.0.0"

# Configuration: Backend PHP API URL
API_BASE_URL = "https://pacewisp.co.ke/api"  # Point this to your PHP API host


def is_internet_available(timeout=2.5):
    """Check if internet connection is active."""
    # Test 1: Google DNS (8.8.8.8)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("8.8.8.8", 53))
        sock.close()
        return True
    except Exception:
        pass

    # Test 2: Cloudflare DNS (1.1.1.1)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("1.1.1.1", 53))
        sock.close()
        return True
    except Exception:
        pass

    # Test 3: HTTP check to pacewisp.co.ke
    try:
        req = urllib.request.Request(
            "https://pacewisp.co.ke",
            headers={"User-Agent": f"Kokonut-Tool/{APP_VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        pass

    return False


def call_php_api(endpoint, payload=None, timeout=10):
    """Make HTTP request to the PHP backend API."""
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"Kokonut-Tool-Client/{APP_VERSION}",
        "Accept": "application/json"
    }

    try:
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        else:
            req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8")
            return json.loads(raw)
        except Exception:
            return {"status": "error", "message": f"HTTP Error {e.code}: {e.reason}"}
    except Exception as ex:
        return {"status": "error", "message": f"Connection to server failed: {str(ex)}"}


class SimpleTelnetClient:
    def __init__(self, host, port=23, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.is_aborted = False

    def connect(self):
        """Create raw socket connection."""
        try:
            self.is_aborted = False
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            return True
        except Exception:
            self.sock = None
            return False

    def send(self, data):
        """Send data over socket."""
        if self.sock and not self.is_aborted:
            try:
                msg = data.strip() + "\r\n"
                self.sock.sendall(msg.encode("utf-8"))
            except Exception:
                pass

    def receive(self, timeout=2):
        """Receive data with a timeout."""
        if not self.sock or self.is_aborted:
            return ""
        self.sock.settimeout(timeout)
        try:
            data = b""
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.is_aborted:
                    break
                try:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b'>' in chunk or b'#' in chunk or b'Login:' in chunk or b'Password:' in chunk:
                        time.sleep(0.05)
                        break
                except socket.timeout:
                    break
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def receive_until(self, patterns, timeout=6):
        """Receive chunks until any of the expected patterns is found or timeout."""
        if not self.sock or self.is_aborted:
            return ""
        self.sock.settimeout(timeout)
        data = ""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_aborted:
                break
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="ignore")
                data += text
                for p in patterns:
                    if p in data:
                        return data
            except socket.timeout:
                break
            except Exception:
                break
        return data

    def login(self, username, password):
        """Log into the Huawei router with robust prompt detection."""
        if not self.connect():
            return False, "Connection failed - unable to reach router at " + self.host

        # Wait for username / login prompt
        banner_data = self.receive_until(["Login:", "login:", "Username:", "username:", "User name:", ":"], timeout=5)
        if self.is_aborted:
            return False, "Operation cancelled"

        # Send username
        self.send(username)
        time.sleep(0.5)

        # Wait for password prompt
        pass_data = self.receive_until(["Password:", "password:", ":"], timeout=4)
        if self.is_aborted:
            return False, "Operation cancelled"

        # Send password
        self.send(password)
        time.sleep(1.0)

        # Wait for command prompt
        prompt_data = self.receive_until([">", "#", "WAP>", "incorrect", "invalid", "failed", "denied", "error"], timeout=5)
        
        lower_resp = (pass_data + prompt_data).lower()
        if "incorrect" in lower_resp or "invalid" in lower_resp or "denied" in lower_resp or "password error" in lower_resp:
            self.close()
            return False, "Login failed - wrong username or password."

        if ">" in prompt_data or "#" in prompt_data:
            return True, "Login successful"

        self.send("")
        time.sleep(0.5)
        check_prompt = self.receive(timeout=2)
        if ">" in check_prompt or "#" in check_prompt:
            return True, "Login successful"

        self.close()
        return False, "Login failed - invalid credentials or timed out."

    def enter_su(self):
        """Enter super user mode."""
        if not self.sock or self.is_aborted:
            return False
        self.send("su")
        time.sleep(1.0)
        resp = self.receive(timeout=3)
        return "ERROR" not in resp

    def remove_security(self, version, ssid_index):
        """Remove security for a given SSID index."""
        results = []
        if version == "5":
            commands = [
                f"set ssid index {ssid_index} security None"
            ]
        else:
            commands = [
                f"set wlan basic laninst 1 wlaninst {ssid_index} beaconType None",
                f"set wlan basic laninst 1 wlaninst {ssid_index} basicauthenticationmode None"
            ]

        for cmd in commands:
            if self.is_aborted:
                results.append(("Aborted", cmd))
                break
            self.send(cmd)
            time.sleep(0.8)
            output = self.receive(2)
            if output and ("ERROR" in output or "ErrCode" in output):
                results.append(("Failed", cmd))
            else:
                results.append(("Success", cmd))

        return results

    def read_wifi_info(self, version):
        """Query router for current WiFi configurations, SSID names, and passwords."""
        wifi_data = []
        if not self.sock or self.is_aborted:
            return wifi_data

        for i in range(1, 9):
            if self.is_aborted:
                break
            info = {
                "index": i,
                "name": f"SSID {i}",
                "security": "Unknown",
                "password": "None / Open",
                "status": "Unknown"
            }
            try:
                if version == "5":
                    self.send(f"display ssid index {i}")
                    time.sleep(0.6)
                    out = self.receive(2)
                    
                    name_match = re.search(r"SSID\s*Name\s*:\s*([^\r\n]+)", out, re.IGNORECASE)
                    if name_match:
                        info["name"] = name_match.group(1).strip()
                    
                    sec_match = re.search(r"Security\s*Mode\s*:\s*([^\r\n]+)", out, re.IGNORECASE)
                    if sec_match:
                        info["security"] = sec_match.group(1).strip()
                    
                    pwd_match = re.search(r"(?:WPA\s*PreSharedKey|PreSharedKey|Key|Password)\s*:\s*([^\r\n]+)", out, re.IGNORECASE)
                    if pwd_match:
                        pwd_val = pwd_match.group(1).strip()
                        if pwd_val and pwd_val != "None" and pwd_val != "******":
                            info["password"] = pwd_val
                        elif "None" in info["security"] or "Open" in info["security"]:
                            info["password"] = "(Open / No Password)"
                    elif "None" in info["security"] or "Open" in info["security"]:
                        info["password"] = "(Open / No Password)"

                else:
                    self.send(f"display wlan basic laninst 1 wlaninst {i}")
                    time.sleep(0.5)
                    basic_out = self.receive(2)
                    
                    name_match = re.search(r"SSID\s*:\s*([^\r\n]+)", basic_out, re.IGNORECASE) or re.search(r"SSID\s*Name\s*:\s*([^\r\n]+)", basic_out, re.IGNORECASE)
                    if name_match:
                        info["name"] = name_match.group(1).strip()
                    
                    sec_match = re.search(r"BeaconType\s*:\s*([^\r\n]+)", basic_out, re.IGNORECASE)
                    if sec_match:
                        info["security"] = sec_match.group(1).strip()
                    
                    self.send(f"display wlan wpa-psk laninst 1 wlaninst {i}")
                    time.sleep(0.5)
                    psk_out = self.receive(2)
                    
                    pwd_match = re.search(r"(?:PreSharedKey|WPA-PSK|Key|Password|wpa-psk)\s*:\s*([^\r\n]+)", psk_out, re.IGNORECASE)
                    if pwd_match:
                        pwd_val = pwd_match.group(1).strip()
                        if pwd_val and pwd_val != "None":
                            info["password"] = pwd_val
                    elif "None" in info["security"] or "Open" in info["security"] or "Basic" in info["security"]:
                        info["password"] = "(Open / No Password)"

            except Exception:
                pass

            wifi_data.append(info)
        return wifi_data

    def save_configuration(self):
        """Save router configuration data."""
        if self.sock and not self.is_aborted:
            self.send("save data")
            time.sleep(1.5)
            self.receive(2)
            self.send("save")
            time.sleep(1.0)
            self.receive(2)
            return True
        return False

    def close(self):
        """Safely close the connection."""
        self.is_aborted = True
        if self.sock:
            try:
                self.send("exit")
                self.send("exit")
                time.sleep(0.2)
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def logout(self):
        self.close()


class TickRadio:
    """A small clickable 'radio button' that shows a tick box (☑ / ☐)."""

    def __init__(self, parent, variable, value, text,
                 accent="#1d4ed8", bg="#ffffff"):
        self.variable = variable
        self.value = value
        self.accent = accent
        self.bg = bg

        self.frame = tk.Frame(parent, bg=bg, cursor="hand2")
        self.mark = tk.Label(self.frame, text="", font=("Segoe UI", 12),
                              bg=bg, width=2)
        self.mark.pack(side=tk.LEFT)
        self.label = tk.Label(self.frame, text=text, font=("Segoe UI", 10), bg=bg)
        self.label.pack(side=tk.LEFT, padx=(2, 0))

        for widget in (self.frame, self.mark, self.label):
            widget.bind("<Button-1>", self._select)

        variable.trace_add("write", lambda *_: self._refresh())
        self._refresh()

    def _select(self, _event=None):
        self.variable.set(self.value)

    def _refresh(self):
        if self.variable.get() == self.value:
            self.mark.config(text="☑", fg=self.accent)
            self.label.config(fg=self.accent, font=("Segoe UI", 10, "bold"))
        else:
            self.mark.config(text="☐", fg="#9aa5b1")
            self.label.config(fg="#1a1a2e", font=("Segoe UI", 10))

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)


class WiFiPasswordsModal:
    """Modal dialog displaying current WiFi SSIDs and passwords read from the router."""
    
    def __init__(self, parent, wifi_info_list):
        self.parent = parent
        self.wifi_info_list = wifi_info_list
        
        self.modal = tk.Toplevel(parent)
        self.modal.title("Router WiFi Passwords & SSIDs")
        self.modal.geometry("640x500")
        self.modal.minsize(580, 420)
        self.modal.configure(bg="#ffffff")
        
        self.modal.transient(parent)
        self.modal.grab_set()
        self._center_modal()
        self._build_ui()
    
    def _center_modal(self):
        self.modal.update_idletasks()
        w = self.modal.winfo_width()
        h = self.modal.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (w // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (h // 2)
        self.modal.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        main = tk.Frame(self.modal, bg="#ffffff", padx=20, pady=18)
        main.pack(fill=tk.BOTH, expand=True)

        hdr = tk.Frame(main, bg="#ffffff")
        hdr.pack(fill=tk.X, pady=(0, 12))

        tk.Label(hdr, text="📶 Current WiFi Passwords & SSIDs",
                 font=("Segoe UI", 15, "bold"), fg="#1d4ed8", bg="#ffffff").pack(anchor=tk.W)
        tk.Label(hdr, text="Live status retrieved from Huawei router.",
                 font=("Segoe UI", 9), fg="#6b7a99", bg="#ffffff").pack(anchor=tk.W)

        tbl_container = tk.Frame(main, bg="#f0f4ff", relief="solid", bd=1, highlightbackground="#c7d7f5")
        tbl_container.pack(fill=tk.BOTH, expand=True, pady=(0, 14))

        canvas = tk.Canvas(tbl_container, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tbl_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#ffffff", padx=10, pady=10)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        hdr_row = tk.Frame(scrollable_frame, bg="#eaf1ff", padx=6, pady=6)
        hdr_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(hdr_row, text="#", font=("Segoe UI", 9, "bold"), width=4, bg="#eaf1ff", anchor="w").pack(side=tk.LEFT)
        tk.Label(hdr_row, text="SSID Name", font=("Segoe UI", 9, "bold"), width=18, bg="#eaf1ff", anchor="w").pack(side=tk.LEFT)
        tk.Label(hdr_row, text="Security Mode", font=("Segoe UI", 9, "bold"), width=15, bg="#eaf1ff", anchor="w").pack(side=tk.LEFT)
        tk.Label(hdr_row, text="Current Password", font=("Segoe UI", 9, "bold"), width=20, bg="#eaf1ff", anchor="w").pack(side=tk.LEFT)
        tk.Label(hdr_row, text="Action", font=("Segoe UI", 9, "bold"), width=8, bg="#eaf1ff", anchor="w").pack(side=tk.LEFT)

        if not self.wifi_info_list:
            tk.Label(scrollable_frame, text="No WiFi information available or router disconnected.",
                     font=("Segoe UI", 10), fg="#c0392b", bg="#ffffff", pady=20).pack()
        else:
            for item in self.wifi_info_list:
                row = tk.Frame(scrollable_frame, bg="#ffffff", padx=6, pady=4, relief="solid", bd=1, highlightbackground="#edf2f7")
                row.pack(fill=tk.X, pady=2)

                tk.Label(row, text=str(item["index"]), font=("Segoe UI", 9, "bold"), width=4, bg="#ffffff", fg="#1d4ed8", anchor="w").pack(side=tk.LEFT)
                tk.Label(row, text=item["name"], font=("Segoe UI", 9), width=18, bg="#ffffff", anchor="w").pack(side=tk.LEFT)
                
                sec_color = "#1a7a3f" if "None" in item["security"] or "Open" in item["security"] else "#1e3a8a"
                tk.Label(row, text=item["security"], font=("Segoe UI", 9), fg=sec_color, width=15, bg="#ffffff", anchor="w").pack(side=tk.LEFT)

                pwd_val = item["password"]
                pwd_fg = "#9aa5b1" if pwd_val.startswith("(") else "#b07d00"
                tk.Label(row, text=pwd_val, font=("Consolas", 9, "bold"), fg=pwd_fg, width=20, bg="#ffffff", anchor="w").pack(side=tk.LEFT)

                def copy_pwd(p=pwd_val):
                    self.modal.clipboard_clear()
                    self.modal.clipboard_append(p)
                    self.modal.update()
                    messagebox.showinfo("Copied", f"Copied password to clipboard:\n{p}", parent=self.modal)

                if not pwd_val.startswith("("):
                    copy_btn = tk.Button(row, text="📋 Copy", font=("Segoe UI", 8),
                                         bg="#f0f4ff", fg="#1d4ed8", relief="flat", padx=6, pady=1,
                                         cursor="hand2", command=copy_pwd)
                    copy_btn.pack(side=tk.LEFT)

        btm = tk.Frame(main, bg="#ffffff")
        btm.pack(fill=tk.X, pady=(5, 0))

        def copy_all_summary():
            lines = ["Huawei Router WiFi Configurations:"]
            for itm in self.wifi_info_list:
                lines.append(f"SSID {itm['index']} ({itm['name']}): Security={itm['security']} | Password={itm['password']}")
            summary = "\n".join(lines)
            self.modal.clipboard_clear()
            self.modal.clipboard_append(summary)
            self.modal.update()
            messagebox.showinfo("Copied", "Full WiFi configuration summary copied to clipboard!", parent=self.modal)

        tk.Button(btm, text="📋 Copy All Details", font=("Segoe UI", 9),
                  bg="#e2e8f0", fg="#1a1a2e", relief="flat", padx=15, pady=5,
                  cursor="hand2", command=copy_all_summary).pack(side=tk.LEFT)

        tk.Button(btm, text="Close", font=("Segoe UI", 9, "bold"),
                  bg="#1d4ed8", fg="white", relief="flat", padx=20, pady=5,
                  cursor="hand2", command=self.modal.destroy).pack(side=tk.RIGHT)


class InAppMpesaModal:
    """In-App M-Pesa STK Push Payment Dialog (Till: 3018584)."""

    def __init__(self, parent, machine_id, is_online=True):
        self.parent = parent
        self.machine_id = machine_id
        self.is_online = is_online
        self.is_polling = False
        self.checkout_request_id = None

        self.modal = tk.Toplevel(parent)
        self.modal.title("Buy Tokens - M-Pesa STK Push")
        self.modal.geometry("520x560")
        self.modal.minsize(480, 500)
        self.modal.configure(bg="#ffffff")

        self.modal.transient(parent)
        self.modal.grab_set()

        self.phone_var = tk.StringVar(value="")
        self.amount_var = tk.StringVar(value="70")

        self._center_modal()
        self._build_ui()
        self.parent.wait_window(self.modal)

    def _center_modal(self):
        self.modal.update_idletasks()
        w = self.modal.winfo_width()
        h = self.modal.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (w // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (h // 2)
        self.modal.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        main = tk.Frame(self.modal, bg="#ffffff", padx=25, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = tk.Frame(main, bg="#ffffff")
        hdr.pack(fill=tk.X, pady=(0, 10))

        tk.Label(hdr, text="💳 M-Pesa Instant STK Push", font=("Segoe UI", 16, "bold"), fg="#16a34a", bg="#ffffff").pack(side=tk.LEFT)

        status_text = "🟢 Online" if self.is_online else "🔴 Offline"
        status_fg = "#065f46" if self.is_online else "#991b1b"
        status_bg = "#ecfdf5" if self.is_online else "#fef2f2"
        tk.Label(hdr, text=status_text, font=("Segoe UI", 8, "bold"), fg=status_fg, bg=status_bg, padx=8, pady=2, relief="solid", bd=1).pack(side=tk.RIGHT)

        tk.Label(main, text="Payment Till: 3018584  |  1 Token = KES 1.00", font=("Segoe UI", 9), fg="#6b7a99", bg="#ffffff").pack(anchor=tk.W, pady=(0, 12))

        # Balance display
        bal_box = tk.Frame(main, bg="#fff8e6", padx=12, pady=8, relief="solid", bd=1, highlightbackground="#fef08a")
        bal_box.pack(fill=tk.X, pady=(0, 14))
        tk.Label(bal_box, text="💎 Current Real-Time Balance:", font=("Segoe UI", 9, "bold"), fg="#854d0e", bg="#fff8e6").pack(side=tk.LEFT)
        self.balance_disp = tk.Label(bal_box, text=f"{getattr(self.parent, 'token_balance', 0)} tokens", font=("Segoe UI", 10, "bold"), fg="#854d0e", bg="#fff8e6")
        self.balance_disp.pack(side=tk.RIGHT)

        # Form
        form = tk.Frame(main, bg="#ffffff")
        form.pack(fill=tk.X, pady=(0, 12))

        # Phone Number
        tk.Label(form, text="M-Pesa Phone Number (e.g., 0712345678 or 254712345678):", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff").pack(anchor=tk.W, pady=(0, 3))
        self.phone_entry = ttk.Entry(form, textvariable=self.phone_var, font=("Segoe UI", 11))
        self.phone_entry.pack(fill=tk.X, pady=(0, 10))

        # Amount in KES
        tk.Label(form, text="Amount in KES (1 Token = KES 1):", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff").pack(anchor=tk.W, pady=(0, 3))
        self.amount_entry = ttk.Entry(form, textvariable=self.amount_var, font=("Segoe UI", 11))
        self.amount_entry.pack(fill=tk.X, pady=(0, 6))

        # Quick preset buttons
        preset_row = tk.Frame(form, bg="#ffffff")
        preset_row.pack(fill=tk.X, pady=(0, 14))

        tk.Button(preset_row, text="KES 70 (V5 Unlock)", font=("Segoe UI", 8), bg="#f1f5f9", relief="flat", padx=8, pady=3, command=lambda: self.amount_var.set("70")).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(preset_row, text="KES 100 (V6 Unlock)", font=("Segoe UI", 8), bg="#f1f5f9", relief="flat", padx=8, pady=3, command=lambda: self.amount_var.set("100")).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(preset_row, text="KES 200", font=("Segoe UI", 8), bg="#f1f5f9", relief="flat", padx=8, pady=3, command=lambda: self.amount_var.set("200")).pack(side=tk.LEFT)

        # Status / Countdown Box
        self.status_box = tk.Frame(main, bg="#f8fafc", padx=12, pady=10, relief="solid", bd=1, highlightbackground="#e2e8f0")
        self.status_box.pack(fill=tk.X, pady=(0, 14))

        self.prompt_label = tk.Label(
            self.status_box,
            text="Ready to initiate STK Push.\nClick 'Send M-Pesa STK Push' below.",
            font=("Segoe UI", 9),
            fg="#475569",
            bg="#f8fafc",
            justify=tk.CENTER
        )
        self.prompt_label.pack(fill=tk.X)

        # Action Buttons
        self.pay_btn = tk.Button(
            main,
            text="📲 Send M-Pesa STK Push",
            font=("Segoe UI", 11, "bold"),
            bg="#16a34a",
            fg="white",
            activebackground="#15803d",
            activeforeground="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._initiate_stk_push
        )
        self.pay_btn.pack(fill=tk.X, pady=(0, 8))

        close_btn = tk.Button(main, text="Close", font=("Segoe UI", 9), bg="#e2e8f0", fg="#475569", relief="flat", padx=15, pady=4, command=self.modal.destroy)
        close_btn.pack()

    def _initiate_stk_push(self):
        """Initiate STK Push via the PHP API backend."""
        phone = self.phone_var.get().strip()
        amount_str = self.amount_var.get().strip()

        if not is_internet_available():
            messagebox.showwarning("Offline", "⚠️ No internet connection detected.\n\nPlease connect to the internet to purchase tokens.", parent=self.modal)
            return

        if not phone:
            messagebox.showwarning("Enter Phone", "Please enter your M-Pesa phone number.", parent=self.modal)
            return

        try:
            amount = int(amount_str)
            if amount < 1:
                raise ValueError()
        except Exception:
            messagebox.showwarning("Invalid Amount", "Please enter a valid amount (minimum KES 1).", parent=self.modal)
            return

        self.pay_btn.config(state=tk.DISABLED, text="Initiating STK Push...")
        self.prompt_label.config(text="Sending STK prompt to your phone...\nPlease wait.", fg="#0284c7")

        def worker():
            res = call_php_api("mpesa_stk.php", {
                "phone": phone,
                "amount": amount,
                "machine_id": self.machine_id,
                "name": "Kokonut Customer"
            })

            if res.get("status") == "success":
                data = res.get("data", {})
                self.checkout_request_id = data.get("CheckoutRequestID")
                self.root_after_safe(lambda: self._start_polling_status(amount))
            else:
                err_msg = res.get("message", "Payment initiation failed.")
                self.root_after_safe(lambda: self._show_initiation_error(err_msg))

        threading.Thread(target=worker, daemon=True).start()

    def root_after_safe(self, callback):
        try:
            self.modal.after(0, callback)
        except Exception:
            pass

    def _show_initiation_error(self, err_msg):
        self.pay_btn.config(state=tk.NORMAL, text="📲 Send M-Pesa STK Push")
        self.prompt_label.config(text=f"❌ Error: {err_msg}", fg="#dc2626")
        messagebox.showerror("Initiation Failed", err_msg, parent=self.modal)

    def _start_polling_status(self, amount):
        self.prompt_label.config(
            text=f"📱 M-Pesa Prompt sent to phone!\n\n"
                 f"Enter your M-Pesa PIN on your phone to complete payment of KES {amount}.\n"
                 f"Waiting for confirmation...",
            fg="#16a34a"
        )
        self.is_polling = True

        def poll_loop():
            start_poll = time.time()
            max_seconds = 65

            while self.is_polling and (time.time() - start_poll < max_seconds):
                time.sleep(3)
                if not self.is_polling:
                    break

                res = call_php_api("mpesa_status.php", {
                    "CheckoutRequestID": self.checkout_request_id
                })

                st = res.get("status", "pending")
                if st == "success":
                    data = res.get("data", {})
                    new_bal = data.get("current_balance", getattr(self.parent, "token_balance", 0) + amount)
                    self.root_after_safe(lambda: self._on_payment_success(amount, new_bal))
                    return
                elif st == "failure":
                    msg = res.get("message", "Payment failed or cancelled.")
                    self.root_after_safe(lambda: self._on_payment_failure(msg))
                    return

            if self.is_polling:
                self.root_after_safe(self._on_payment_timeout)

        threading.Thread(target=poll_loop, daemon=True).start()

    def _on_payment_success(self, amount, new_balance):
        self.is_polling = False
        self.parent.token_balance = new_balance
        self.balance_disp.config(text=f"{new_balance} tokens")
        if hasattr(self.parent, "token_label"):
            self.parent.token_label.config(text=f"💎 {new_balance} tokens")
        if hasattr(self.parent, "balance_label"):
            self.parent.balance_label.config(text=f"{new_balance} tokens")
        if hasattr(self.parent, "_log"):
            self.parent._log(f"✅ M-Pesa payment confirmed: +{amount} tokens! New balance: {new_balance} tokens.", "ok")

        self.prompt_label.config(text=f"🎉 Payment Successful!\n+{amount} tokens credited to your account.", fg="#16a34a")
        self.pay_btn.config(state=tk.NORMAL, text="📲 Send M-Pesa STK Push")
        messagebox.showinfo("Payment Successful", f"✅ Payment Received!\n\n+{amount} Tokens have been added to your account.\nTotal Balance: {new_balance} tokens.", parent=self.modal)

    def _on_payment_failure(self, msg):
        self.is_polling = False
        self.prompt_label.config(text=f"❌ Payment Failed:\n{msg}", fg="#dc2626")
        self.pay_btn.config(state=tk.NORMAL, text="📲 Send M-Pesa STK Push")
        messagebox.showerror("Payment Failed", f"Payment was not completed.\n\nReason: {msg}", parent=self.modal)

    def _on_payment_timeout(self):
        self.is_polling = False
        self.prompt_label.config(text="⏱ Payment verification timed out.\nIf you entered your PIN, click Sync Balance.", fg="#ca8a04")
        self.pay_btn.config(state=tk.NORMAL, text="📲 Send M-Pesa STK Push")


class VersionBlockedModal:
    """Dialog displayed when the app version is outdated or blocked by administrator."""

    def __init__(self, parent, message, download_url):
        self.parent = parent
        self.message = message
        self.download_url = download_url

        self.modal = tk.Toplevel(parent)
        self.modal.title("Application Update Required")
        self.modal.geometry("480x320")
        self.modal.resizable(False, False)
        self.modal.configure(bg="#ffffff")

        self.modal.transient(parent)
        self.modal.grab_set()

        # Center dialog
        self.modal.update_idletasks()
        w = self.modal.winfo_width()
        h = self.modal.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (w // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (h // 2)
        self.modal.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        main = tk.Frame(self.modal, bg="#ffffff", padx=25, pady=25)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="⛔ Update Required", font=("Segoe UI", 16, "bold"), fg="#dc2626", bg="#ffffff").pack(pady=(0, 10))

        tk.Label(
            main,
            text=self.message,
            font=("Segoe UI", 10),
            fg="#1e293b",
            bg="#ffffff",
            wraplength=420,
            justify=tk.CENTER
        ).pack(pady=(0, 20))

        # Download Update Button
        tk.Button(
            main,
            text="🌐 Download Latest Version",
            font=("Segoe UI", 11, "bold"),
            bg="#1d4ed8",
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._open_download
        ).pack(fill=tk.X, pady=(0, 10))

        tk.Button(
            main,
            text="Exit Application",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#475569",
            relief="flat",
            padx=15,
            pady=4,
            command=self.parent.destroy
        ).pack()

    def _open_download(self):
        if self.download_url:
            webbrowser.open(self.download_url)


class RouterApp:
    ROUTER_IP = "192.168.100.1"
    PORT = 23

    # Blue theme
    ACCENT = "#1d4ed8"       # primary blue
    ACCENT_DARK = "#1e3a8a"  # pressed/hover blue
    ACCENT_LIGHT = "#eaf1ff" # tinted panel background
    BORDER = "#c7d7f5"
    BG = "#ffffff"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"KOKONUT v{APP_VERSION}")
        self.root.geometry("780x780")
        self.root.minsize(680, 680)
        self.root.configure(bg=self.BG)

        # Get machine ID on startup & hardware lock check
        self.machine_id = get_machine_id()
        self.machine_info = get_machine_info()
        
        self.version = tk.StringVar(value="5")
        self.username = tk.StringVar(value="root")
        
        # User enters password manually (no hardcoded password)
        self.password = tk.StringVar(value="")
        self.password_visible = tk.BooleanVar(value=False)
        self.ssid_vars = {}
        self.client = None
        
        # Online / Offline tracking & Version enforcement
        self.is_online = False
        self.is_version_blocked = False
        self.network_thread = None
        
        # Flag to track if operation is in progress
        self.is_operation_running = False
        self.operation_thread = None
        self.is_connected = False
        self.stop_requested = threading.Event()
        
        # Token balance (synced from DB)
        self.token_balance = 0
        
        # Unlock costs
        self.V5_UNLOCK_COST = 70
        self.V6_UNLOCK_COST = 100

        self._setup_styles()
        self._build_ui()
        
        # Start background network connectivity monitor, version verification, & balance sync
        self._start_network_monitor()
        
        # Set up the close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Log machine information
        self._log(f"Kokonut Router Tool v{APP_VERSION}", "ok")
        self._log(f"Machine ID: {self.machine_id[:8]}... (Hardware bound)", "dim")
        self._log(f"System: {self.machine_info['system']}", "dim")
        self._log(f"🔓 V5 unlock: {self.V5_UNLOCK_COST} tokens  |  🔓 V6 unlock: {self.V6_UNLOCK_COST} tokens", "dim")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure(".", background=self.BG, foreground="#1a1a2e", font=("Segoe UI", 10))
        style.configure("TFrame", background=self.BG)
        style.configure("TLabelframe", background=self.BG, bordercolor=self.BORDER, relief="solid")
        style.configure("TLabelframe.Label", background=self.BG, foreground=self.ACCENT_DARK,
                         font=("Segoe UI", 9, "bold"))

        style.configure("TCheckbutton", background=self.BG, foreground="#1a1a2e",
                         font=("Segoe UI", 10))
        style.map("TCheckbutton",
                  indicatorcolor=[("selected", self.ACCENT), ("!selected", "#ffffff")])

        style.configure("TButton", background=self.ACCENT_LIGHT, foreground=self.ACCENT_DARK,
                         bordercolor=self.BORDER, relief="solid", padding=(10, 6),
                         font=("Segoe UI", 10))
        style.map("TButton",
                  background=[("active", "#dbe6ff"), ("disabled", "#f3f6fc")],
                  foreground=[("disabled", "#aab4c8")])

        style.configure("Primary.TButton", background=self.ACCENT, foreground="#ffffff",
                         bordercolor=self.ACCENT, font=("Segoe UI", 10, "bold"), padding=(10, 7))
        style.map("Primary.TButton",
                  background=[("active", self.ACCENT_DARK), ("disabled", "#a9c0f0")],
                  foreground=[("disabled", "#eef2fb")])

    def _start_network_monitor(self):
        """Start a background thread to check internet connection and sync live balance."""
        def monitor():
            while True:
                online = is_internet_available(timeout=2.0)
                if online != self.is_online:
                    self.is_online = online
                    self.root.after(0, self._update_network_ui)
                
                if online:
                    self._check_version_and_sync()

                time.sleep(8)

        self.network_thread = threading.Thread(target=monitor, daemon=True)
        self.network_thread.start()

    def _check_version_and_sync(self):
        """Check app version policy and sync real-time balance."""
        try:
            # Re-verify hardware integrity (anti-cloning check)
            if not verify_machine_id():
                self.root.after(0, lambda: self._log("⚠️ Hardware mismatch detected! Tokens cannot be transferred.", "err"))
                return

            # 1. Version Check
            ver_res = call_php_api("check_version.php", {
                "app_version": APP_VERSION,
                "machine_id": self.machine_id
            })

            if ver_res.get("status") == "blocked" or (ver_res.get("data", {}).get("is_allowed") is False):
                self.is_version_blocked = True
                msg = ver_res.get("message", "This version of the application has been deprecated or blocked.")
                dl_url = ver_res.get("data", {}).get("download_url", "https://pacewisp.co.ke/download")
                self.root.after(0, lambda: self._handle_version_blocked(msg, dl_url))
                return

            # 2. Device & Balance Sync
            dev_res = call_php_api("device.php", {
                "machine_id": self.machine_id,
                "app_version": APP_VERSION,
                "system_info": self.machine_info
            })

            if dev_res.get("status") == "success":
                data = dev_res.get("data", {})
                live_bal = int(data.get("token_balance", 0))
                self.token_balance = live_bal
                self.root.after(0, self._update_balance_labels)
        except Exception:
            pass

    def _handle_version_blocked(self, msg, dl_url):
        """Disable operations when version is blocked."""
        self.remove_btn.config(state=tk.DISABLED, text="⛔ Update Required")
        self.connect_btn.config(state=tk.DISABLED)
        self.net_badge.config(text="⛔ Version Blocked", fg="#dc2626", bg="#fef2f2")
        self._log(f"⛔ {msg}", "err")
        VersionBlockedModal(self.root, msg, dl_url)

    def _update_balance_labels(self):
        self.token_label.config(text=f"💎 {self.token_balance} tokens")
        self.balance_label.config(text=f"{self.token_balance} tokens")

    def _update_network_ui(self):
        """Update online/offline badge in the UI."""
        if self.is_version_blocked:
            return

        if self.is_online:
            self.net_badge.config(
                text="🟢 Online",
                fg="#065f46",
                bg="#ecfdf5",
                highlightbackground="#a7f3d0"
            )
            self._log("🌐 Connected to internet. Real-time token sync active.", "ok")
        else:
            self.net_badge.config(
                text="🔴 Offline",
                fg="#991b1b",
                bg="#fef2f2",
                highlightbackground="#fecaca"
            )
            self._log("⚠️ Offline: Connect to internet to buy tokens or unlock routers.", "warn")

    def _connect_to_router(self):
        """Connect to the router."""
        if self.is_version_blocked:
            messagebox.showerror("Update Required", "Application version is no longer supported. Please update.", parent=self.root)
            return False

        if self.is_connected and self.client and self.client.sock:
            return True
        
        pwd = self.password.get()
        usr = self.username.get().strip()
        
        if not usr:
            messagebox.showwarning("Missing Username", "Please enter the router username (e.g., root).", parent=self.root)
            return False
            
        if not pwd:
            messagebox.showwarning("Missing Password", "Please enter the router password in the Login box.", parent=self.root)
            return False
        
        self._log(f"Connecting to {self.ROUTER_IP}:{self.PORT}...", "dim")
        self._set_status("Connecting...", "#b07d00")
        
        self.client = SimpleTelnetClient(self.ROUTER_IP, self.PORT, timeout=10)
        ok, msg = self.client.login(usr, pwd)
        
        if not ok:
            self._log(f"Connection failed: {msg}", "err")
            self._set_status("Disconnected", "#c0392b")
            self.is_connected = False
            self.client = None
            return False
        
        self._log("✓ Authenticated successfully", "ok")
        self._set_status("Connected", "#1a7a3f")
        self.is_connected = True
        
        su_ok = self.client.enter_su()
        if su_ok:
            self._log("✓ Super user mode activated", "dim")
        else:
            self._log("Notice: Standard prompt ready", "dim")
        
        return True

    def _disconnect_from_router(self):
        """Disconnect from the router."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        
        self.is_connected = False
        self._set_status("Disconnected", "#c0392b")
        self._log("Disconnected from router", "dim")

    def _open_token_modal(self):
        """Open the In-App M-Pesa STK Push purchase modal."""
        InAppMpesaModal(self.root, self.machine_id, is_online=self.is_online)
        self._update_balance_labels()

    def _toggle_password(self):
        """Toggle password visibility between masked and plain text."""
        self.password_visible.set(not self.password_visible.get())
        if self.password_visible.get():
            self.pass_entry.config(show="")
            self.eye_btn.config(text="👁‍🗨 Hide", fg="#1d4ed8", bg="#eaf1ff")
        else:
            self.pass_entry.config(show="•")
            self.eye_btn.config(text="👁 Show", fg="#6b7a99", bg=self.BG)

    def _copy_machine_id(self):
        """Copy machine ID to clipboard with confirmation."""
        if messagebox.askyesno("Copy Machine ID", 
                               "This will copy the full machine ID to your clipboard.\n\n"
                               "⚠️ Only share this ID with authorized support personnel."):
            self.root.clipboard_clear()
            self.root.clipboard_append(self.machine_id)
            self.root.update()
            self._log("📋 Machine ID copied to clipboard (use with caution)", "warn")
            self.id_label.config(foreground="#b07d00")
            self.root.after(2000, lambda: self.id_label.config(foreground="#6b7a99"))

    def _view_current_passwords(self):
        """Read and view current WiFi SSIDs and passwords from router."""
        if self.is_operation_running:
            messagebox.showwarning("Busy", "Another operation is running. Please wait.", parent=self.root)
            return

        if not self.password.get():
            messagebox.showwarning("Enter Password", "Please enter the router password in the Login box first.", parent=self.root)
            return

        self.is_operation_running = True
        self.stop_requested.clear()
        self.remove_btn.config(state=tk.DISABLED)
        self.view_pwd_btn.config(state=tk.DISABLED, text="Reading...")
        self._set_status("Reading WiFi info...", "#b07d00")

        def worker():
            try:
                if not self.is_connected or not self.client:
                    self._log("Connecting to router to read WiFi passwords...", "dim")
                    if not self._connect_to_router():
                        self.root.after(0, lambda: messagebox.showerror("Connection Failed", "Unable to connect to router. Check your IP, username, and password.", parent=self.root))
                        return

                version = self.version.get()
                self._log(f"Fetching current WiFi status for Version {version}...", "dim")
                wifi_info = self.client.read_wifi_info(version)

                if self.stop_requested.is_set():
                    self._log("WiFi reading aborted.", "warn")
                    return

                self._log("✓ WiFi configuration retrieved:", "ok")
                for w in wifi_info:
                    pwd_display = w['password']
                    self._log(f"  SSID {w['index']} [{w['name']}]: {w['security']} | Pass: {pwd_display}", "dim")

                self.root.after(0, lambda: WiFiPasswordsModal(self.root, wifi_info))
                self._set_status("Connected", "#1a7a3f")

            except Exception as e:
                self._log(f"Error reading passwords: {str(e)}", "err")
                self._set_status("Error", "#c0392b")
            finally:
                self.is_operation_running = False
                self.root.after(0, self._reset_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _build_ui(self):
        root_pad = ttk.Frame(self.root, padding="20 16 20 16")
        root_pad.pack(fill=tk.BOTH, expand=True)

        # Header with token button and Online/Offline badge
        hdr = ttk.Frame(root_pad)
        hdr.pack(fill=tk.X, pady=(0, 10))

        title_frame = tk.Frame(hdr, bg=self.BG)
        title_frame.pack(side=tk.LEFT)
        ttk.Label(title_frame, text=f"KOKONUT v{APP_VERSION}",
                  font=("Segoe UI", 15, "bold"), foreground=self.ACCENT).pack(side=tk.LEFT)

        # Online/Offline badge in header
        self.net_badge = tk.Label(
            title_frame, text="⏳ Checking...",
            font=("Segoe UI", 8, "bold"),
            fg="#6b7a99", bg="#f0f4ff",
            padx=8, pady=2, relief="solid", bd=1,
            highlightbackground="#c7d7f5",
            cursor="hand2"
        )
        self.net_badge.pack(side=tk.LEFT, padx=(12, 0))
        self.net_badge.bind("<Button-1>", lambda e: self._check_network_manual())

        # Token button in header
        token_frame = tk.Frame(hdr, bg=self.BG)
        token_frame.pack(side=tk.RIGHT)
        
        self.token_label = tk.Label(token_frame, text="💎 0 tokens", 
                                   font=("Segoe UI", 9, "bold"),
                                   fg=self.ACCENT_DARK, bg=self.BG,
                                   cursor="hand2")
        self.token_label.pack(side=tk.RIGHT, padx=(0, 10))
        self.token_label.bind("<Button-1>", lambda e: self._open_token_modal())
        
        # Buy tokens button
        buy_btn = tk.Button(token_frame, text="Buy Tokens (KES 1/token)", 
                           font=("Segoe UI", 8, "bold"),
                           bg="#f59e0b", fg="white",
                           relief="flat", padx=12, pady=3,
                           cursor="hand2",
                           command=self._open_token_modal)
        buy_btn.pack(side=tk.RIGHT)

        # Machine ID Card
        id_card = tk.Frame(root_pad, bg=self.ACCENT_LIGHT, relief="solid", bd=1, highlightbackground=self.BORDER)
        id_card.pack(fill=tk.X, pady=(0, 14))

        id_inner = tk.Frame(id_card, bg=self.ACCENT_LIGHT, padx=15, pady=10)
        id_inner.pack(fill=tk.X)

        id_left = tk.Frame(id_inner, bg=self.ACCENT_LIGHT)
        id_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(id_left, text="🔑 MACHINE ID (partial)", 
                font=("Segoe UI", 8, "bold"), fg=self.ACCENT_DARK, bg=self.ACCENT_LIGHT).pack(anchor=tk.W)

        id_row = tk.Frame(id_left, bg=self.ACCENT_LIGHT)
        id_row.pack(anchor=tk.W, fill=tk.X)

        partial_id = f"{self.machine_id[:8]}••••{self.machine_id[-4:]}"
        self.id_label = tk.Label(id_row, text=partial_id, 
                                font=("Consolas", 12, "bold"), 
                                fg="#1a1a2e", bg=self.ACCENT_LIGHT)
        self.id_label.pack(side=tk.LEFT)

        copy_btn = tk.Button(id_row, text="📋 Copy Full ID", 
                            font=("Segoe UI", 8),
                            bg=self.ACCENT, fg="white",
                            relief="flat", padx=10, pady=2,
                            cursor="hand2",
                            command=self._copy_machine_id)
        copy_btn.pack(side=tk.LEFT, padx=(10, 0))

        id_right = tk.Frame(id_inner, bg=self.ACCENT_LIGHT)
        id_right.pack(side=tk.RIGHT)

        tk.Label(id_right, text=self.machine_info.get('system', 'Unknown'),
                font=("Segoe UI", 9), fg="#6b7a99", bg=self.ACCENT_LIGHT).pack(anchor=tk.E)

        hw_info = []
        if 'windows_build' in self.machine_info:
            hw_info.append(f"Build: {self.machine_info['windows_build']}")
        if 'cpu_count' in self.machine_info:
            hw_info.append(f"CPU: {self.machine_info['cpu_count']} cores")
        
        if hw_info:
            tk.Label(id_right, text=" | ".join(hw_info),
                    font=("Segoe UI", 8), fg="#9aa5b1", bg=self.ACCENT_LIGHT).pack(anchor=tk.E)

        sep = tk.Frame(root_pad, bg=self.ACCENT, height=2)
        sep.pack(fill=tk.X, pady=(0, 14))

        # Connection status bar with Connect and Disconnect buttons
        conn_bar = tk.Frame(root_pad, bg="#f0f4ff", padx=12, pady=8, relief="solid", bd=1, highlightbackground=self.BORDER)
        conn_bar.pack(fill=tk.X, pady=(0, 10))
        
        status_frame = tk.Frame(conn_bar, bg="#f0f4ff")
        status_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Router Connection Status indicator
        self.status_dot = tk.Label(status_frame, text="●", 
                                  font=("Segoe UI", 14),
                                  fg="#c0392b", bg="#f0f4ff")
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_text = tk.Label(status_frame, text="Disconnected", 
                                   font=("Segoe UI", 10, "bold"),
                                   fg="#c0392b", bg="#f0f4ff")
        self.status_text.pack(side=tk.LEFT)
        
        # Connect & Disconnect buttons
        btn_frame = tk.Frame(conn_bar, bg="#f0f4ff")
        btn_frame.pack(side=tk.RIGHT)
        
        self.connect_btn = tk.Button(btn_frame, text="⚡ Connect", 
                                    font=("Segoe UI", 9, "bold"),
                                    bg="#10b981", fg="white",
                                    activebackground="#059669", activeforeground="white",
                                    relief="flat", padx=14, pady=5,
                                    cursor="hand2",
                                    command=self._connect_click)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 6))
        
        self.disconnect_btn = tk.Button(btn_frame, text="🔌 Disconnect", 
                                       font=("Segoe UI", 9, "bold"),
                                       bg="#ef4444", fg="white",
                                       activebackground="#dc2626", activeforeground="white",
                                       relief="flat", padx=14, pady=5,
                                       cursor="hand2",
                                       command=self._disconnect_click)
        self.disconnect_btn.pack(side=tk.LEFT)

        # Token balance bar
        balance_bar = tk.Frame(root_pad, bg="#f0f4ff", padx=12, pady=6)
        balance_bar.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(balance_bar, text="💎 Live Token Balance:", 
                font=("Segoe UI", 9, "bold"), 
                fg=self.ACCENT_DARK, bg="#f0f4ff").pack(side=tk.LEFT)
        
        self.balance_label = tk.Label(balance_bar, text="0 tokens", 
                                     font=("Segoe UI", 9, "bold"), 
                                     fg=self.ACCENT_DARK, bg="#f0f4ff")
        self.balance_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Unlock costs
        tk.Label(balance_bar, text="|  🔓 V5: 70 tokens (KES 70)  |  🔓 V6: 100 tokens (KES 100)", 
                font=("Segoe UI", 8), 
                fg="#6b7a99", bg="#f0f4ff").pack(side=tk.LEFT, padx=(15, 0))
        
        tk.Label(balance_bar, text="Click 'Buy Tokens' to pay with M-Pesa", 
                font=("Segoe UI", 8), 
                fg="#6b7a99", bg="#f0f4ff").pack(side=tk.RIGHT)

        # Warning
        warn_frame = tk.Frame(root_pad, bg="#fff8e6", relief="flat", bd=0)
        warn_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(warn_frame,
                 text="⚠ Warning: Selected SSIDs will have their passwords removed and become open networks.",
                 bg="#fff8e6", fg="#7a5800", font=("Segoe UI", 9),
                 anchor="w", pady=7, padx=10, wraplength=700, justify="left").pack(fill=tk.X)

        # Two-column row
        row = ttk.Frame(root_pad)
        row.pack(fill=tk.X, pady=(0, 14))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        version_frame = ttk.LabelFrame(row, text="Router model", padding="10 8")
        version_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        v5 = TickRadio(version_frame, self.version, "5", "HG8145V5 (version 5) - 70 tokens",
                        accent=self.ACCENT, bg=self.BG)
        v5.pack(anchor=tk.W, pady=2)
        v6 = TickRadio(version_frame, self.version, "6", "HG8145V6 (version 6) - 100 tokens",
                        accent=self.ACCENT, bg=self.BG)
        v6.pack(anchor=tk.W, pady=2)

        conn_frame = ttk.LabelFrame(row, text="Login", padding="10 8")
        conn_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ttk.Label(conn_frame, text=f"{self.ROUTER_IP} : {self.PORT}",
                  font=("Segoe UI", 9), foreground="#9aa5b1").pack(anchor=tk.W, pady=(0, 6))

        ttk.Label(conn_frame, text="Username", font=("Segoe UI", 8),
                  foreground="#6b7a99").pack(anchor=tk.W)
        user_entry = ttk.Entry(conn_frame, textvariable=self.username, font=("Segoe UI", 10))
        user_entry.pack(anchor=tk.W, fill=tk.X, pady=(0, 6))

        ttk.Label(conn_frame, text="Password (enter router password)", font=("Segoe UI", 8),
                  foreground="#6b7a99").pack(anchor=tk.W)
        
        pass_frame = tk.Frame(conn_frame, bg=self.BG)
        pass_frame.pack(anchor=tk.W, fill=tk.X)

        self.pass_entry = ttk.Entry(pass_frame, textvariable=self.password, show="•", font=("Segoe UI", 10))
        self.pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Eye toggle button to view/hide password
        self.eye_btn = tk.Button(pass_frame, text="👁 Show", 
                                font=("Segoe UI", 8, "bold"),
                                bg=self.BG, fg="#6b7a99",
                                relief="flat", padx=6, pady=2,
                                cursor="hand2",
                                activebackground="#eaf1ff",
                                command=self._toggle_password)
        self.eye_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # SSID selection
        ssid_frame = ttk.LabelFrame(root_pad, text="Select SSIDs to modify", padding="10 8")
        ssid_frame.pack(fill=tk.X, pady=(0, 14))

        info_frame = ttk.Frame(ssid_frame)
        info_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(info_frame, text="Note: Each SSID index is modified independently.",
                  font=("Segoe UI", 8), foreground="#6b7a99").pack(anchor=tk.W)

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

        # View Current WiFi Passwords button
        self.view_pwd_btn = tk.Button(action_row, text="👁 View WiFi Passwords",
                                     font=("Segoe UI", 9, "bold"),
                                     bg="#0284c7", fg="white",
                                     relief="flat", padx=12, pady=6,
                                     cursor="hand2",
                                     command=self._view_current_passwords)
        self.view_pwd_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(action_row, text="Clear log", command=self._clear_log).pack(side=tk.LEFT)
        ttk.Button(action_row, text="Verify ID", command=self._verify_id).pack(side=tk.LEFT, padx=(8, 0))

        # Log
        log_frame = ttk.LabelFrame(root_pad, text="Log", padding="6 4")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log = scrolledtext.ScrolledText(
            log_frame, height=8, wrap=tk.WORD,
            font=("Consolas", 9), relief="flat", bd=0,
            background="#f5f8ff", foreground="#28324a"
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.tag_config("ok", foreground="#1a7a3f")
        self.log.tag_config("err", foreground="#c0392b")
        self.log.tag_config("dim", foreground="#9aa5b1")
        self.log.tag_config("warn", foreground="#b07d00")

    # ------------------------------------------------------------------ helpers

    def _check_network_manual(self):
        """Manually trigger a network check and balance sync."""
        self.net_badge.config(text="⏳ Checking...", fg="#6b7a99", bg="#f0f4ff")
        def check():
            online = is_internet_available()
            self.is_online = online
            self.root.after(0, self._update_network_ui)
            if online:
                self._check_version_and_sync()
        threading.Thread(target=check, daemon=True).start()

    def _connect_click(self):
        """Handle connect button click."""
        self._connect_to_router()
    
    def _disconnect_click(self):
        """Handle disconnect button click."""
        if self.is_operation_running:
            messagebox.showwarning(
                "Operation in Progress",
                "Cannot disconnect while an operation is running.",
                parent=self.root
            )
            return
        
        if not self.is_connected and not self.client:
            self._log("Notice: Router is already disconnected.", "dim")
            return
            
        self._disconnect_from_router()

    def _set_status(self, text, color="#9aa5b1"):
        """Update router connection status display."""
        if text == "Connected":
            self.status_dot.config(fg="#10b981")
            self.status_text.config(text="Connected", fg="#10b981")
        elif text == "Disconnected":
            self.status_dot.config(fg="#c0392b")
            self.status_text.config(text="Disconnected", fg="#c0392b")
        else:
            self.status_dot.config(fg="#f59e0b")
            self.status_text.config(text=text, fg="#f59e0b")

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

    def _verify_id(self):
        if verify_machine_id():
            messagebox.showinfo("Verification", 
                              f"✅ Machine ID Verified\n\n"
                              f"ID: {self.machine_id}\n\n"
                              f"The ID is consistent with this physical machine.",
                              parent=self.root)
        else:
            messagebox.showwarning("Verification Failed",
                                 "❌ Hardware mismatch detected!\n\n"
                                 "This machine ID belongs to different hardware and cannot be copied.",
                                 parent=self.root)

    # ------------------------------------------------------------------ main action

    def _run(self):
        if self.is_version_blocked:
            messagebox.showerror("Update Required", "Application version is outdated or blocked. Please download the update.", parent=self.root)
            return

        selected = [i for i in range(1, 9) if self.ssid_vars[i].get()]

        if not selected:
            messagebox.showwarning("Nothing selected", "Select at least one SSID.", parent=self.root)
            return

        if not self.password.get():
            messagebox.showwarning("Enter Password", "Please enter the router password in the Login box first.", parent=self.root)
            return

        # STRICT ONLINE CHECK: App MUST be online to initiate real-time unlock
        if not is_internet_available():
            messagebox.showerror(
                "Internet Required",
                "⚠️ You must be connected to the internet to authorize password removal.\n\n"
                "Please connect to the internet and try again.",
                parent=self.root
            )
            return

        # Hardware integrity check (anti-cloning)
        if not verify_machine_id():
            messagebox.showerror(
                "Hardware Mismatch",
                "❌ Hardware verification failed.\n\n"
                "This application is locked to this machine and cannot be copied or spoofed.",
                parent=self.root
            )
            return

        version = self.version.get()
        required_tokens = self.V5_UNLOCK_COST if version == "5" else self.V6_UNLOCK_COST

        self.is_operation_running = True
        self.stop_requested.clear()
        
        # Disable action buttons
        self.remove_btn.config(state=tk.DISABLED, text="Authorizing...")
        self.view_pwd_btn.config(state=tk.DISABLED)

        def worker():
            session_id = None
            configured_ssids = []
            try:
                # 1. Initiate unlock on PHP API backend (Atomic Token Reservation with Version Check)
                self._log(f"Authorizing unlock with backend server ({required_tokens} tokens)...", "dim")
                init_res = call_php_api("initiate_unlock.php", {
                    "machine_id": self.machine_id,
                    "version": version,
                    "app_version": APP_VERSION
                })

                if init_res.get("status") != "success":
                    err_msg = init_res.get("message", "Authorization failed.")
                    self._log(f"✗ Authorization failed: {err_msg}", "err")
                    self.root.after(0, lambda: messagebox.showwarning("Unlock Denied", err_msg, parent=self.root))
                    if "Insufficient" in err_msg:
                        self.root.after(0, self._open_token_modal)
                    return

                init_data = init_res.get("data", {})
                session_id = init_data.get("session_id")
                new_bal = init_data.get("new_balance", self.token_balance - required_tokens)
                self.token_balance = new_bal
                self.root.after(0, self._update_balance_labels)
                self._log(f"✓ Authorization approved. Tokens reserved. Session: {session_id[:12]}...", "ok")

                # 2. Connect to Router
                if not self.is_connected or not self.client or not self.client.sock:
                    self._log("Connecting to router...", "dim")
                    if not self._connect_to_router():
                        self._log("✗ Could not connect to router. Requesting token refund...", "err")
                        # Refund tokens via API
                        if session_id:
                            call_php_api("confirm_unlock.php", {
                                "session_id": session_id,
                                "machine_id": self.machine_id,
                                "success": False,
                                "ssids_done": []
                            })
                            self._sync_live_device_status()
                        self.root.after(0, lambda: messagebox.showerror("Router Connection Failed", "Unable to connect to router. Check IP and password.\nTokens were not deducted.", parent=self.root))
                        return

                self._log(f"Starting password removal for Version {version} router...", "warn")
                self._set_status("Removing passwords...", "#b07d00")
                self._log(f"Selected SSIDs: {', '.join(str(s) for s in selected)}", "dim")

                # 3. Process SSIDs
                for ssid in selected:
                    if self.stop_requested.is_set():
                        self._log("⛔ Process interrupted by user.", "warn")
                        break

                    self._log(f"Processing SSID {ssid}...", "dim")
                    results = self.client.remove_security(version, ssid)
                    
                    all_ok = all(status == "Success" for status, _ in results)
                    if all_ok:
                        self._log(f"✓ SSID {ssid} — password removed", "ok")
                        configured_ssids.append(ssid)
                    else:
                        self._log(f"✗ SSID {ssid} — command failed", "err")
                    time.sleep(0.5)

                # 4. Save Configuration on Router
                if configured_ssids:
                    self._log("Saving configuration to flash...", "dim")
                    self.client.save_configuration()
                    self._log(f"✓ Done! {len(configured_ssids)} SSID(s) are now open networks.", "ok")
                else:
                    self._log("✗ No SSIDs were modified.", "err")

                # 5. Confirm Unlock Session with Backend API
                if session_id:
                    self._log("Confirming unlock completion with backend API...", "dim")
                    confirm_res = call_php_api("confirm_unlock.php", {
                        "session_id": session_id,
                        "machine_id": self.machine_id,
                        "success": len(configured_ssids) > 0,
                        "ssids_done": configured_ssids
                    })
                    if confirm_res.get("status") == "success":
                        self._log("✓ Backend database updated in real-time.", "ok")
                    self._sync_live_device_status()

                if self.is_connected:
                    self._set_status("Connected", "#1a7a3f")
                
            except Exception as e:
                self._log(f"Error: {str(e)}", "err")
                self._set_status("Error", "#c0392b")
                # Ensure server session is notified
                if session_id:
                    try:
                        call_php_api("confirm_unlock.php", {
                            "session_id": session_id,
                            "machine_id": self.machine_id,
                            "success": len(configured_ssids) > 0,
                            "ssids_done": configured_ssids
                        })
                    except Exception:
                        pass
            finally:
                self.is_operation_running = False
                self.root.after(0, self._reset_ui)

        # Start worker thread
        self.operation_thread = threading.Thread(target=worker, daemon=True)
        self.operation_thread.start()

    def _reset_ui(self):
        """Reset the UI after operation completes."""
        self.remove_btn.config(state=tk.NORMAL, text="Remove passwords")
        self.view_pwd_btn.config(state=tk.NORMAL, text="👁 View WiFi Passwords")

    # ------------------------------------------------------------------ lifecycle

    def _on_close(self):
        """Handle window close event with protection."""
        if self.is_operation_running:
            if messagebox.askyesno(
                "Operation in Progress",
                "⚠️ An operation is currently running.\n\n"
                "Do you want to stop the operation and exit?",
                parent=self.root
            ):
                self.stop_requested.set()
                if self.client:
                    self.client.close()
            else:
                return
        
        if self.is_connected:
            self._disconnect_from_router()
        
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RouterApp().run()