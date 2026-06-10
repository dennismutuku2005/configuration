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
    
    def configure_huawei(self, username, password, version="5", start_index=1, end_index=12345678):
        """Configure Huawei router for a range of indexes"""
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
            print(f"Processing indexes {start_index} through {end_index}")
            
            # First, enter su mode if needed
            if version == "6":
                self.send("su")
                time.sleep(1)
                self.receive(2)
            
            # Loop through all indexes
            for index in range(start_index, end_index + 1):
                print(f"\n{'='*60}")
                print(f"Processing index {index}...")
                
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
                    print(f"  Executing: {cmd}")
                    self.send(cmd)
                    time.sleep(1.5)
                    output = self.receive(2)
                    if output:
                        print(f"  Response: {output[:100]}...")
                
                # Optional: Show progress every 1000 indexes
                if index % 1000 == 0:
                    print(f"  ✓ Completed {index} indexes so far...")
            
            # Final display and save
            print(f"\n{'='*60}")
            print("All indexes configured! Showing final config...")
            self.send("display wlan config")
            time.sleep(3)
            final_output = self.receive(5)
            print(f"Final config output: {final_output[:500]}...")
            
            # Save configuration
            print("\nSaving configuration...")
            self.send("save")
            time.sleep(2)
            save_response = self.receive(3)
            print(f"Save response: {save_response[:200]}...")
            
            print(f"\n✓ Configuration complete for indexes {start_index} through {end_index}!")
            
            # Exit
            self.send("exit")
            if version == "6":
                self.send("exit")
            time.sleep(1)
        
        self.sock.close()
        return True


# Usage
if __name__ == "__main__":
    print("Huawei Router Configuration Utility")
    print("1. Version 5")
    print("2. Version 6")
    choice = input("Select version (1 or 2, default 1): ").strip()
    
    version = "6" if choice == "2" else "5"
    
    # Optional: Customize index range
    custom_range = input("Use custom index range? (y/n, default n): ").strip().lower()
    
    start_idx = 1
    end_idx = 12345678
    
    if custom_range == 'y':
        try:
            start_idx = int(input(f"Start index (default 1): ") or "1")
            end_idx = int(input(f"End index (default 12345678): ") or "12345678")
        except ValueError:
            print("Invalid input, using defaults")
    
    print(f"\nStarting configuration for indexes {start_idx} to {end_idx}")
    print("WARNING: This will configure a large number of indexes and may take significant time!")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        client = SimpleTelnetClient("192.168.100.1", port=23, timeout=10)
        client.configure_huawei("root", "Muuo02593.", version=version, 
                                start_index=start_idx, end_index=end_idx)
    else:
        print("Operation cancelled.")