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
    
    def configure_huawei(self, username, password):
        """Configure Huawei router"""
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
            print("Login successful!")
            
            # Execute commands
            commands = [
                "su",
                "set ssid index 1 security None",
                "set ssid index 5 security None",
                "display wlan config",
                "save"
            ]
            
            results = []
            for cmd in commands:
                print(f"Executing: {cmd}")
                self.send(cmd)
                time.sleep(2)
                output = self.receive(3)
                results.append(f"\n{'='*50}\nCommand: {cmd}\nOutput:\n{output}")
                print(f"Response received: {len(output)} characters")
            
            # Save results
            with open('socket_config_results.txt', 'w') as f:
                f.write("\n".join(results))
            
            print("\nConfiguration complete! Saved to socket_config_results.txt")
            
            # Exit
            self.send("exit")
            self.send("exit")
            time.sleep(1)
        
        self.sock.close()
        return True


# Usage
if __name__ == "__main__":
    client = SimpleTelnetClient("192.168.100.1", port=23, timeout=10)
    client.configure_huawei("root", "Muuo02593.")