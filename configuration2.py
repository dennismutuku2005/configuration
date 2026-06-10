import socket
import time
import sys

class SimpleTelnetClient:
    def __init__(self, host, port=23, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        
    def connect(self):
        """Create raw socket connection"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def send(self, data):
        """Send data"""
        if self.sock:
            self.sock.send(data.encode() + b'\n')
    
    def receive(self, timeout=2):
        """Receive data with timeout"""
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
                # Check if we have a complete response (ends with prompt)
                if b'>' in chunk or b':' in chunk:
                    time.sleep(0.1)
                    break
            return data.decode('utf-8', errors='ignore')
        except socket.timeout:
            return ""
        except Exception:
            return ""
    
    def configure_huawei(self, username, password, version="5", start_index=1, end_index=8):
        """Configure Huawei router for indexes 1-8 only"""
        if not self.connect():
            return False
            
        print(f"Connected to {self.host}")
        
        # Read initial banner
        banner = self.receive(5)
        print("Banner received")
        
        # Send username
        if "Login:" in banner or "login:" in banner:
            self.send(username)
        else:
            # Wait for login prompt
            time.sleep(1)
            self.send(username)
        
        # Read password prompt
        response = self.receive(3)
        print(f"After username: {response[:100]}...")
        
        # Send password
        self.send(password)
        
        # Wait for command prompt
        time.sleep(2)
        prompt = self.receive(3)
        print(f"After password: {prompt[:100]}...")
        
        if ">" in prompt or "#" in prompt:
            print(f"Login successful! Configuring for Version {version}...")
            print(f"Processing indexes {start_index} through {end_index} (TOTAL: {end_index - start_index + 1} indexes)")
            
            # First, enter su mode if needed
            if version == "6":
                self.send("su")
                time.sleep(1)
                self.receive(2)
            
            # Loop through indexes 1 to 8
            for index in range(start_index, end_index + 1):
                print(f"\n{'='*50}")
                print(f"📡 Processing index {index}...")
                
                if version == "6":
                    # Version 6 commands with index
                    commands = [
                        f"set wlan basic laninst {index} wlaninst {index} beaconType None",
                        f"set wlan basic laninst {index} wlaninst {index} basicauthenticationmode None",
                        f"set wlan basic laninst {index} wlaninst {index+4} beaconType None",
                        f"set wlan basic laninst {index} wlaninst {index+4} basicauthenticationmode None"
                    ]
                else:
                    # Version 5 commands with index
                    commands = [
                        f"set ssid index {index} security None"
                    ]
                
                # Execute commands for this index
                for cmd in commands:
                    print(f"  ▶ Executing: {cmd}")
                    self.send(cmd)
                    time.sleep(1.5)
                    output = self.receive(2)
                    if output:
                        print(f"  ✓ Response: {output[:100]}...")
                    else:
                        print(f"  ✓ Command sent successfully")
            
            # Show final configuration
            print(f"\n{'='*50}")
            print("✅ All 8 indexes configured!")
            print(f"{'='*50}")
            
            # Optional: Show current SSID settings
            print("\n📋 Showing current SSID configuration...")
            self.send("display ssid all" if version == "5" else "display wlan config")
            time.sleep(3)
            final_output = self.receive(5)
            print(f"\nCurrent configuration:\n{final_output[:500]}")
            
            # Save configuration
            print("\n💾 Saving configuration to router...")
            self.send("save")
            time.sleep(2)
            save_response = self.receive(3)
            print(f"Save result: {save_response[:200]}")
            
            print(f"\n{'='*50}")
            print(f"✨ COMPLETE! ✨")
            print(f"Configured indexes: {start_index} through {end_index}")
            print(f"WiFi security set to: NONE (Open network)")
            print(f"{'='*50}")
            
            # Exit
            self.send("exit")
            if version == "6":
                self.send("exit")
            time.sleep(1)
        
        self.sock.close()
        return True


# Usage
if __name__ == "__main__":
    print("="*50)
    print("   HUAWEI ROUTER CONFIGURATOR")
    print("   Configure SSID Indexes 1-8")
    print("="*50)
    print("\n⚠️  WARNING: This will DISABLE WiFi passwords")
    print("   All configured SSIDs will become OPEN networks")
    print("\nWhat this script does:")
    print("  • Version 5: Sets SSID index 1-8 security to 'None'")
    print("  • Version 6: Sets WLAN instances 1-8 and 5-12 to open mode")
    print("="*50)
    
    print("\n1. Version 5 (Older Huawei routers)")
    print("2. Version 6 (Newer Huawei routers)")
    choice = input("\nSelect version (1 or 2): ").strip()
    
    version = "6" if choice == "2" else "5"
    
    # Fixed for indexes 1-8 only
    start_idx = 1
    end_idx = 8
    
    print(f"\n📊 Configuration plan:")
    print(f"  • Router IP: 192.168.100.1")
    print(f"  • Version: {version}")
    print(f"  • Indexes: {start_idx} to {end_idx} (8 total)")
    print(f"  • Action: Remove WiFi security")
    
    confirm = input("\n⚠️  Continue? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        print("\n🚀 Starting configuration...\n")
        client = SimpleTelnetClient("192.168.100.1", port=23, timeout=10)
        client.configure_huawei("root", "Muuo02593.", version=version, 
                                start_index=start_idx, end_index=end_idx)
    else:
        print("❌ Operation cancelled.")