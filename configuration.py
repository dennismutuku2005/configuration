import warnings
import telnetlib
import time

# Suppress deprecation warning (temporary solution)
warnings.filterwarnings("ignore", category=DeprecationWarning)

HOST = "192.168.100.1"
USERNAME = "root"
PASSWORD = "Muuo02593."

# Correct Huawei command structure
commands = [
    "su",
    "set ssid index 1 security None",
    "set ssid index 5 security None"
]

def send_command(tn, cmd, expected_prompt=b"SU_WAP>", timeout=2):
    """Helper function to send command and wait for prompt and"""
    tn.write(cmd.encode('ascii') + b"\n")
    time.sleep(0.5)  # Short delay for command processing
    return tn.read_until(expected_prompt, timeout=timeout).decode('ascii')

try:
    print(f"Connecting to {HOST}...")
    tn = telnetlib.Telnet(HOST, timeout=10)

    # Login process
    tn.read_until(b"Login: ", timeout=5)
    tn.write(USERNAME.encode('ascii') + b"\n")
    
    tn.read_until(b"Password: ", timeout=5)
    tn.write(PASSWORD.encode('ascii') + b"\n")
    
    # Wait for initial prompt
    tn.read_until(b"WAP>", timeout=5)
    
    # Execute commands
    output = ""
    for cmd in commands:
        print(f"Executing: {cmd}")
        response = send_command(tn, cmd)
        output += f"\nCommand: {cmd}\nResponse: {response}\n"
        if "ERROR" in response:
            print(f"⚠️ Command failed: {cmd}")
    
    # Verify changes
    output += "\nVerification:\n"
    output += send_command(tn, "display wlan config")
    
    # Clean exit
    tn.write(b"exit\n")
    tn.write(b"exit\n")
    output += tn.read_all().decode('ascii')
    
    print("✅ Configuration completed. Output:\n", output)

except Exception as e:
    print("❌ Error occurred:", str(e))
finally:
    if 'tn' in locals():
        tn.close()