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
                if b'>' in chunk or b':' in chunk or b'#' in chunk:
                    time.sleep(0.1)
                    break
            return data.decode('utf-8', errors='ignore')
        except socket.timeout:
            return ""
        except Exception:
            return ""
    
    def configure_huawei(self, username, password, version="5", start_index=1, end_index=8):
        """Configure Huawei router for indexes 1-8"""
        if not self.connect():
            return False
            
        print(f"Connected to {self.host}")
        
        # Login
        banner = self.receive(5)
        print("Connected, logging in...")
        
        if "Login:" in banner or "login:" in banner:
            self.send(username)
        else:
            time.sleep(1)
            self.send(username)
        
        time.sleep(1)
        response = self.receive(3)
        self.send(password)
        time.sleep(2)
        prompt = self.receive(3)
        
        if ">" not in prompt and "#" not in prompt:
            print("Login failed!")
            self.sock.close()
            return False
        
        print(f"✅ Login successful! Configuring Version {version}")
        
        # Enter su mode for BOTH versions (Version 5 and 6 both need su)
        print("Entering super user mode...")
        self.send("su")
        time.sleep(2)
        su_response = self.receive(2)
        if "ERROR" in su_response:
            print("Warning: Could not enter su mode, but continuing...")
        else:
            print("✓ SU mode activated")
        
        # Process indexes
        print(f"Processing indexes {start_index} through {end_index}")
        
        for index in range(start_index, end_index + 1):
            print(f"\n{'='*50}")
            print(f"📡 Processing index {index}...")
            
            if version == "5":
                # VERSION 5 COMMANDS (with index and index+4)
                commands = [
                    f"set ssid index {index} security None",
                    f"set ssid index {index+4} security None"
                ]
                print("  Using Version 5 commands")
                
            elif version == "6":
                # VERSION 6 COMMANDS (with laninst 1)
                commands = [
                    f"set wlan basic laninst 1 wlaninst {index} beaconType None",
                    f"set wlan basic laninst 1 wlaninst {index} basicauthenticationmode None",
                    f"set wlan basic laninst 1 wlaninst {index+4} beaconType None",
                    f"set wlan basic laninst 1 wlaninst {index+4} basicauthenticationmode None"
                ]
                print("  Using Version 6 commands")
            
            # Execute commands for this index
            for cmd in commands:
                print(f"  ▶ {cmd}")
                self.send(cmd)
                time.sleep(1)
                output = self.receive(2)
                
                if output and "ERROR" in output:
                    print(f"  ✗ Failed")
                elif output and "ErrCode" in output:
                    print(f"  ✗ Error")
                else:
                    print(f"  ✓ Success")
        
        # Show final configuration
        print(f"\n{'='*50}")
        print("📋 Displaying final configuration...")
        self.send("display wlan config")
        time.sleep(3)
        final_output = self.receive(5)
        if final_output and "ERROR" not in final_output:
            print(f"\n{final_output[:500]}")
        
        # Save configuration
        print("\n💾 Saving configuration...")
        self.send("save")
        time.sleep(2)
        save_response = self.receive(3)
        print(f"✓ Save completed")
        
        print(f"\n{'='*50}")
        print(f"✨ CONFIGURATION COMPLETE! ✨")
        print(f"Version: {version}")
        print(f"Configured indexes: {start_index} through {end_index}")
        if version == "5":
            print(f"SSID indexes: {start_index}-{end_index} and {start_index+4}-{end_index+4}")
        else:
            print(f"WLAN instances: {start_index}-{end_index} and {start_index+4}-{end_index+4}")
        print(f"WiFi security: NONE (Open network)")
        print(f"{'='*50}")
        
        # Exit
        self.send("exit")
        self.send("exit")
        time.sleep(1)
        
        self.sock.close()
        return True


# Usage
if __name__ == "__main__":
    print("="*55)
    print("     HUAWEI ROUTER CONFIGURATOR")
    print("     Version 5 AND Version 6 Support")
    print("="*55)
    
    print("\n⚠️  WARNING: This removes ALL WiFi passwords!")
    print("   Networks become OPEN with NO security")
    
    print("\n" + "="*55)
    print("SELECT ROUTER VERSION:")
    print("="*55)
    print("  1. Version 5 (set ssid index X security None)")
    print("  2. Version 6 (set wlan basic laninst 1 wlaninst X)")
    print("="*55)
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        version = "5"
        print("\n✅ Version 5 selected")
        print("   Commands pattern:")
        print("   - set ssid index X security None")
        print("   - set ssid index X+4 security None")
    elif choice == "2":
        version = "6"
        print("\n✅ Version 6 selected")
        print("   Commands pattern:")
        print("   - set wlan basic laninst 1 wlaninst X beaconType None")
        print("   - set wlan basic laninst 1 wlaninst X basicauthenticationmode None")
    else:
        print("Invalid choice, using Version 5")
        version = "5"
    
    # Index range selection
    print("\n" + "="*55)
    print("SELECT INDEX RANGE:")
    print("="*55)
    print("  1. Index 1 only (configures 1 and 5)")
    print("  2. Indexes 1-4 (configures 1-4 and 5-8)")
    print("  3. Indexes 1-8 (configures 1-8 and 5-12)")
    print("  4. Custom range")
    print("="*55)
    
    range_choice = input("\nEnter choice (1-4, default 1): ").strip()
    
    if range_choice == "1":
        start_idx, end_idx = 1, 1
    elif range_choice == "2":
        start_idx, end_idx = 1, 4
    elif range_choice == "3":
        start_idx, end_idx = 1, 8
    elif range_choice == "4":
        try:
            start_idx = int(input("Start index (default 1): ") or "1")
            end_idx = int(input("End index (default 8): ") or "8")
        except:
            start_idx, end_idx = 1, 1
    else:
        start_idx, end_idx = 1, 1
    
    print(f"\n{'='*55}")
    print("CONFIGURATION PLAN:")
    print(f"{'='*55}")
    print(f"  • Router IP:     192.168.100.1")
    print(f"  • Version:       {version}")
    print(f"  • Index range:   {start_idx} to {end_idx}")
    
    if version == "5":
        print(f"  • Will configure:")
        print(f"    - SSID {start_idx} to {end_idx}")
        print(f"    - SSID {start_idx+4} to {end_idx+4}")
    else:
        print(f"  • Will configure:")
        print(f"    - WLAN {start_idx} to {end_idx}")
        print(f"    - WLAN {start_idx+4} to {end_idx+4}")
    
    print(f"  • Action:        Remove ALL WiFi security")
    print(f"{'='*55}")
    
    confirm = input("\n⚠️  CONTINUE? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        print("\n🚀 STARTING CONFIGURATION...\n")
        client = SimpleTelnetClient("192.168.100.1", port=23, timeout=10)
        client.configure_huawei("root", "Muuo02593.", 
                                version=version, 
                                start_index=start_idx, 
                                end_index=end_idx)
    else:
        print("\n❌ Operation cancelled.")