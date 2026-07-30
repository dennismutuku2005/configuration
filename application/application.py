import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import time
import threading
from datetime import datetime
import json
import os
import webbrowser

# Import the machine ID module
from machine_id import get_machine_id, get_machine_info, verify_machine_id


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
            commands = [
                f"set ssid index {ssid_index} security None"
            ]
        else:
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


class TickRadio:
    """A small clickable 'radio button' that shows a tick box (☑ / ☐)
    instead of the default OS radio dot."""

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


class TokenPurchaseModal:
    """Modal dialog for purchasing KOKONUT tokens."""
    
    def __init__(self, parent, machine_id):
        self.parent = parent
        self.machine_id = machine_id
        self.result = None
        
        # Create modal window
        self.modal = tk.Toplevel(parent)
        self.modal.title("Buy KOKONUT Tokens")
        self.modal.geometry("480x380")
        self.modal.resizable(False, False)
        self.modal.configure(bg="#ffffff")
        
        # Make it modal
        self.modal.transient(parent)
        self.modal.grab_set()
        
        # Center on parent
        self._center_modal()
        
        self._build_ui()
        
        # Wait for modal to close
        self.parent.wait_window(self.modal)
    
    def _center_modal(self):
        """Center the modal on the parent window."""
        self.modal.update_idletasks()
        width = self.modal.winfo_width()
        height = self.modal.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (width // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (height // 2)
        self.modal.geometry(f"{width}x{height}+{x}+{y}")
    
    def _build_ui(self):
        # Main container
        main_frame = tk.Frame(self.modal, bg="#ffffff", padx=30, pady=25)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = tk.Frame(main_frame, bg="#ffffff")
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(header_frame, text="💰 Buy KOKONUT Tokens", 
                font=("Segoe UI", 18, "bold"), 
                fg="#1d4ed8", bg="#ffffff").pack(anchor=tk.W)
        
        tk.Label(header_frame, text="1 Token = KES 1.00", 
                font=("Segoe UI", 10), 
                fg="#6b7a99", bg="#ffffff").pack(anchor=tk.W)
        
        # Machine ID display
        id_frame = tk.Frame(main_frame, bg="#f0f4ff", padx=12, pady=8, 
                           relief="solid", bd=1, highlightbackground="#c7d7f5")
        id_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(id_frame, text="🔑 Machine ID", 
                font=("Segoe UI", 8, "bold"), 
                fg="#6b7a99", bg="#f0f4ff").pack(anchor=tk.W)
        
        tk.Label(id_frame, text=self.machine_id, 
                font=("Consolas", 10), 
                fg="#1a1a2e", bg="#f0f4ff").pack(anchor=tk.W)
        
        # Description
        tk.Label(main_frame, 
                text="Purchase tokens to enable password removal functionality.\n"
                     "Unlock costs:",
                font=("Segoe UI", 10), 
                fg="#4a5568", bg="#ffffff", justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 5))
        
        # Unlock costs
        cost_frame = tk.Frame(main_frame, bg="#f8fafc", padx=10, pady=5)
        cost_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(cost_frame, text="🔓 V5 Router: 70 tokens (KES 70)", 
                font=("Segoe UI", 9), 
                fg="#1a1a2e", bg="#f8fafc").pack(side=tk.LEFT, padx=10)
        
        tk.Label(cost_frame, text="🔓 V6 Router: 100 tokens (KES 100)", 
                font=("Segoe UI", 9), 
                fg="#1a1a2e", bg="#f8fafc").pack(side=tk.LEFT, padx=10)
        
        # Buy button
        buy_frame = tk.Frame(main_frame, bg="#ffffff")
        buy_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = tk.Label(buy_frame, 
                text="Click the button below to open the payment page.\n"
                     "You can enter any amount you wish to purchase.",
                font=("Segoe UI", 9), 
                fg="#4a5568", bg="#ffffff", justify=tk.CENTER)
        info_text.pack(pady=(0, 10))
        
        buy_btn = tk.Button(buy_frame, text="🛒 Buy Tokens", 
                           font=("Segoe UI", 12, "bold"),
                           bg="#f59e0b", fg="white",
                           relief="flat", padx=40, pady=10,
                           cursor="hand2",
                           command=self._buy_tokens)
        buy_btn.pack()
        
        # Current balance
        balance_frame = tk.Frame(main_frame, bg="#fff8e6", padx=12, pady=8)
        balance_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(balance_frame, text="💎 Your Balance", 
                font=("Segoe UI", 9, "bold"), 
                fg="#7a5800", bg="#fff8e6").pack(side=tk.LEFT)
        
        self.balance_label = tk.Label(balance_frame, text="0 tokens", 
                                     font=("Segoe UI", 10, "bold"), 
                                     fg="#7a5800", bg="#fff8e6")
        self.balance_label.pack(side=tk.RIGHT)
        
        # Close button
        close_btn = tk.Button(main_frame, text="Close", 
                             font=("Segoe UI", 10),
                             bg="#e2e8f0", fg="#4a5568",
                             relief="flat", padx=20, pady=5,
                             cursor="hand2",
                             command=self.modal.destroy)
        close_btn.pack(pady=(5, 0))
        
        # Fetch initial balance
        self._fetch_balance()
    
    def _buy_tokens(self):
        """Open the token purchase page with machine ID."""
        url = f"https://pacewisp.co.ke/buytokens?machine_id={self.machine_id}"
        
        # Open in browser
        webbrowser.open(url)
        
        # Show confirmation
        messagebox.showinfo(
            "Purchase Started",
            f"🌐 Opening payment page.\n\n"
            f"Machine ID: {self.machine_id}\n\n"
            f"1 Token = KES 1.00\n"
            f"You can enter any amount you wish to purchase.\n\n"
            f"Complete the payment on the website.\n"
            f"Tokens will be added to your account automatically.",
            parent=self.modal
        )
        
        # Simulate balance update (dummy - in production this would be from API)
        self._simulate_balance_update(10)  # Dummy: add 10 tokens for testing
    
    def _simulate_balance_update(self, tokens_added):
        """Dummy function to simulate token balance update."""
        current = int(self.balance_label.cget("text").split()[0])
        new_balance = current + tokens_added
        self.balance_label.config(text=f"{new_balance} tokens")
        
        # Update parent balance if available
        if hasattr(self.parent, 'token_balance'):
            self.parent.token_balance = new_balance
            if hasattr(self.parent, 'token_label'):
                self.parent.token_label.config(text=f"💎 {new_balance} tokens")
            if hasattr(self.parent, 'balance_label'):
                self.parent.balance_label.config(text=f"{new_balance} tokens")
        
        # Log in the main app
        if hasattr(self.parent, '_log'):
            self.parent._log(f"💰 Tokens updated: +{tokens_added} tokens (KES {tokens_added})", "ok")
            self.parent._log(f"💎 New balance: {new_balance} tokens", "dim")
    
    def _fetch_balance(self):
        """Fetch token balance from API (dummy)."""
        # In production, this would be an API call to:
        # https://pacewisp.co.ke/api/balance?machine_id={machine_id}
        
        # Use parent balance if available
        if hasattr(self.parent, 'token_balance'):
            self.balance_label.config(text=f"{self.parent.token_balance} tokens")
        else:
            # Dummy data - start with 0 tokens
            dummy_balance = 0
            self.balance_label.config(text=f"{dummy_balance} tokens")


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
        self.root.title("KOKONUT")
        self.root.geometry("750x750")
        self.root.minsize(680, 650)
        self.root.configure(bg=self.BG)

        # Get machine ID on startup
        self.machine_id = get_machine_id()
        self.machine_info = get_machine_info()
        
        self.version = tk.StringVar(value="5")
        self.username = tk.StringVar(value="root")
        self.password = tk.StringVar(value="")
        self.password_visible = tk.BooleanVar(value=False)
        self.ssid_vars = {}
        self.client = None
        
        # Flag to track if operation is in progress
        self.is_operation_running = False
        self.operation_thread = None
        self.is_connected = False
        
        # Token balance (starts at 0)
        self.token_balance = 0
        
        # Unlock costs
        self.V5_UNLOCK_COST = 70
        self.V6_UNLOCK_COST = 100

        self._setup_styles()
        self._build_ui()
        
        # Set up the close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Log machine information
        self._log(f"Machine ID: {self.machine_id[:8]}... (full ID stored securely)", "dim")
        self._log(f"System: {self.machine_info['system']}", "dim")
        self._log(f"💎 Token balance: {self.token_balance} tokens", "dim")
        self._log(f"🔓 V5 unlock: {self.V5_UNLOCK_COST} tokens (KES {self.V5_UNLOCK_COST})", "dim")
        self._log(f"🔓 V6 unlock: {self.V6_UNLOCK_COST} tokens (KES {self.V6_UNLOCK_COST})", "dim")

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

    def _connect_to_router(self):
        """Connect to the router."""
        if self.is_connected:
            self._log("Already connected", "warn")
            return True
        
        if not self.username.get().strip() or not self.password.get():
            messagebox.showwarning("Missing credentials", "Enter a username and password.")
            return False
        
        self._log(f"Connecting to {self.ROUTER_IP}:{self.PORT}...", "dim")
        self._set_status("Connecting...", "#b07d00")
        
        self.client = SimpleTelnetClient(self.ROUTER_IP, self.PORT, timeout=10)
        ok, msg = self.client.login(self.username.get().strip(), self.password.get())
        
        if not ok:
            self._log(f"Connection failed: {msg}", "err")
            self._set_status("Disconnected", "#c0392b")
            self.is_connected = False
            return False
        
        self._log("Authenticated", "ok")
        self._set_status("Connected", "#1a7a3f")
        self.is_connected = True
        
        # Enter super user mode
        self.client.send("su")
        time.sleep(2)
        self.client.receive(2)
        self._log("Super user mode active", "dim")
        
        return True

    def _disconnect_from_router(self):
        """Disconnect from the router."""
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
            self.client = None
        
        self.is_connected = False
        self._set_status("Disconnected", "#9aa5b1")
        self._log("Disconnected", "dim")

    def _open_token_modal(self):
        """Open the token purchase modal."""
        TokenPurchaseModal(self.root, self.machine_id)
        # Refresh token display after modal closes
        self.token_label.config(text=f"💎 {self.token_balance} tokens")
        self.balance_label.config(text=f"{self.token_balance} tokens")

    def _toggle_password(self):
        """Toggle password visibility."""
        self.password_visible.set(not self.password_visible.get())
        if self.password_visible.get():
            self.pass_entry.config(show="")
            self.eye_btn.config(text="⊙")
        else:
            self.pass_entry.config(show="•")
            self.eye_btn.config(text="◉")

    def _copy_machine_id(self):
        """Copy machine ID to clipboard with confirmation."""
        if messagebox.askyesno("Copy Machine ID", 
                               "This will copy the full machine ID to your clipboard.\n\n"
                               "⚠️ Only share this ID with authorized support personnel."):
            self.root.clipboard_clear()
            self.root.clipboard_append(self.machine_id)
            self.root.update()
            self._log(f"📋 Machine ID copied to clipboard (use with caution)", "warn")
            self.id_label.config(foreground="#b07d00")
            self.root.after(2000, lambda: self.id_label.config(foreground="#6b7a99"))

    def _build_ui(self):
        root_pad = ttk.Frame(self.root, padding="20 16 20 16")
        root_pad.pack(fill=tk.BOTH, expand=True)

        # Header with token button
        hdr = ttk.Frame(root_pad)
        hdr.pack(fill=tk.X, pady=(0, 10))

        title_frame = tk.Frame(hdr, bg=self.BG)
        title_frame.pack(side=tk.LEFT)
        ttk.Label(title_frame, text="KOKONUT",
                  font=("Segoe UI", 15, "bold"), foreground=self.ACCENT).pack(side=tk.LEFT)

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

        self.status_label = ttk.Label(hdr, text="  Disconnected",
                                       font=("Segoe UI", 9), foreground="#9aa5b1")
        self.status_label.pack(side=tk.RIGHT, pady=(4, 0))

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

        # Connection status bar with Connect/Disconnect buttons
        conn_bar = tk.Frame(root_pad, bg="#f0f4ff", padx=12, pady=6)
        conn_bar.pack(fill=tk.X, pady=(0, 10))
        
        status_frame = tk.Frame(conn_bar, bg="#f0f4ff")
        status_frame.pack(side=tk.LEFT)
        
        # Status indicator
        self.status_dot = tk.Label(status_frame, text="●", 
                                  font=("Segoe UI", 14),
                                  fg="#c0392b", bg="#f0f4ff")
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_text = tk.Label(status_frame, text="Disconnected", 
                                   font=("Segoe UI", 9, "bold"),
                                   fg="#c0392b", bg="#f0f4ff")
        self.status_text.pack(side=tk.LEFT)
        
        # Connect/Disconnect buttons
        btn_frame = tk.Frame(conn_bar, bg="#f0f4ff")
        btn_frame.pack(side=tk.RIGHT)
        
        self.connect_btn = tk.Button(btn_frame, text="Connect", 
                                    font=("Segoe UI", 9, "bold"),
                                    bg="#10b981", fg="white",
                                    relief="flat", padx=15, pady=4,
                                    cursor="hand2",
                                    command=self._connect_click)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.disconnect_btn = tk.Button(btn_frame, text="Disconnect", 
                                       font=("Segoe UI", 9, "bold"),
                                       bg="#ef4444", fg="white",
                                       relief="flat", padx=15, pady=4,
                                       cursor="hand2",
                                       command=self._disconnect_click)
        self.disconnect_btn.pack(side=tk.LEFT)
        self.disconnect_btn.config(state=tk.DISABLED)

        # Token balance bar
        balance_bar = tk.Frame(root_pad, bg="#f0f4ff", padx=12, pady=6)
        balance_bar.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(balance_bar, text="💎 Token Balance:", 
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
        
        tk.Label(balance_bar, text="Click 'Buy Tokens' to add more", 
                font=("Segoe UI", 8), 
                fg="#6b7a99", bg="#f0f4ff").pack(side=tk.RIGHT)

        # Warning
        warn_frame = tk.Frame(root_pad, bg="#fff8e6", relief="flat", bd=0)
        warn_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(warn_frame,
                 text="⚠ Warning: Selected SSIDs will have their passwords removed and become open networks.",
                 bg="#fff8e6", fg="#7a5800", font=("Segoe UI", 9),
                 anchor="w", pady=7, padx=10, wraplength=680, justify="left").pack(fill=tk.X)

        # Two-column row
        row = ttk.Frame(root_pad)
        row.pack(fill=tk.X, pady=(0, 14))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        version_frame = ttk.LabelFrame(row, text="Router model", padding="10 8")
        version_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        v5 = TickRadio(version_frame, self.version, "5", f"HG8145V5 (version 5) - 70 tokens",
                        accent=self.ACCENT, bg=self.BG)
        v5.pack(anchor=tk.W, pady=2)
        v6 = TickRadio(version_frame, self.version, "6", f"HG8145V6 (version 6) - 100 tokens",
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

        ttk.Label(conn_frame, text="Password", font=("Segoe UI", 8),
                  foreground="#6b7a99").pack(anchor=tk.W)
        
        pass_frame = tk.Frame(conn_frame, bg=self.BG)
        pass_frame.pack(anchor=tk.W, fill=tk.X)

        self.pass_entry = ttk.Entry(pass_frame, textvariable=self.password, show="•", font=("Segoe UI", 10))
        self.pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.eye_btn = tk.Button(pass_frame, text="◉", 
                                font=("Segoe UI", 12),
                                bg=self.BG, fg="#6b7a99",
                                relief="flat", width=3,
                                cursor="hand2",
                                activebackground=self.BG,
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

    def _connect_click(self):
        """Handle connect button click."""
        if self._connect_to_router():
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.status_dot.config(fg="#10b981")
            self.status_text.config(text="Connected", fg="#10b981")
    
    def _disconnect_click(self):
        """Handle disconnect button click."""
        if self.is_operation_running:
            messagebox.showwarning(
                "Operation in Progress",
                "Cannot disconnect while an operation is running.",
                parent=self.root
            )
            return
        
        self._disconnect_from_router()
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.status_dot.config(fg="#c0392b")
        self.status_text.config(text="Disconnected", fg="#c0392b")

    def _set_status(self, text, color="#9aa5b1"):
        """Update status display."""
        self.status_label.config(text=f"  {text}", foreground=color)
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
                              f"The ID is consistent with this system.")
        else:
            messagebox.showwarning("Verification Failed",
                                 "❌ The machine ID appears to be different from the current system.\n\n"
                                 "This might happen if you've changed hardware or operating system.")

    # ------------------------------------------------------------------ main action

    def _run(self):
        selected = [i for i in range(1, 9) if self.ssid_vars[i].get()]

        if not selected:
            messagebox.showwarning("Nothing selected", "Select at least one SSID.")
            return

        # Check if connected
        if not self.is_connected:
            messagebox.showwarning("Not Connected", 
                                 "Please connect to the router first.\n\n"
                                 "Click the 'Connect' button above.")
            return

        # Calculate required tokens based on router version
        version = self.version.get()
        required_tokens = self.V5_UNLOCK_COST if version == "5" else self.V6_UNLOCK_COST
        
        # Check token balance
        if self.token_balance < required_tokens:
            messagebox.showwarning(
                "Insufficient Tokens",
                f"You need {required_tokens} tokens to unlock {version} router.\n"
                f"Current balance: {self.token_balance} tokens.\n\n"
                f"1 Token = KES 1.00\n"
                f"You need KES {required_tokens} to unlock.\n\n"
                f"Please buy more tokens to continue."
            )
            # Open token modal automatically
            self._open_token_modal()
            return

        # Set operation flag BEFORE starting thread
        self.is_operation_running = True
        
        # Disable buttons
        self.remove_btn.config(state=tk.DISABLED, text="Working...")
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.DISABLED)

        def worker():
            try:
                self._log(f"Starting unlock for {version} router...", "warn")
                self._set_status("Unlocking...", "#b07d00")
                
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
                    
                    # Deduct tokens
                    self.token_balance -= required_tokens
                    self.token_label.config(text=f"💎 {self.token_balance} tokens")
                    self.balance_label.config(text=f"{self.token_balance} tokens")
                    
                    self._log(f"✓ Done. {success_count} SSID(s) are now open.", "warn")
                    self._log(f"💎 Tokens remaining: {self.token_balance}", "dim")
                    self._log(f"💰 Tokens used: {required_tokens} (KES {required_tokens})", "dim")
                else:
                    self._log("✗ No SSIDs were configured successfully.", "err")
                    self._log("💎 No tokens were deducted (operation failed)", "warn")

                self._set_status("Connected", "#1a7a3f")
                
            except Exception as e:
                self._log(f"Error: {str(e)}", "err")
                self._set_status("Error", "#c0392b")
            finally:
                # Reset the operation flag when done
                self.is_operation_running = False
                # Re-enable buttons
                self.root.after(0, self._reset_ui)

        # Start the thread
        self.operation_thread = threading.Thread(target=worker, daemon=True)
        self.operation_thread.start()

    def _reset_ui(self):
        """Reset the UI after operation completes."""
        self.remove_btn.config(state=tk.NORMAL, text="Remove passwords")
        if self.is_connected:
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
        else:
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ lifecycle

    def _on_close(self):
        """Handle window close event with protection."""
        # Check if operation is running
        if self.is_operation_running:
            messagebox.showwarning(
                "Operation in Progress",
                "⚠️ Cannot close the application while passwords are being removed.\n\n"
                "Please wait for the operation to complete before closing.",
                parent=self.root
            )
            return
        
        # Check if thread is still alive (safety check)
        if self.operation_thread and self.operation_thread.is_alive():
            messagebox.showwarning(
                "Operation in Progress",
                "⚠️ A process is still running.\n\n"
                "Please wait for it to complete before closing.",
                parent=self.root
            )
            return
        
        # Safe to close - disconnect if connected
        if self.is_connected:
            self._disconnect_from_router()
        
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RouterApp().run()