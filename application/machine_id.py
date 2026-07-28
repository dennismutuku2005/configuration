# machine_id.py
import hashlib
import json
import os
import platform
import socket
import sys
import uuid
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


class MachineID:
    """
    Generate and manage a persistent unique ID for the machine using 
    ONLY truly permanent hardware identifiers.
    
    Uses:
    - CPU ID/Serial (built into CPU)
    - Motherboard Serial (physical hardware)
    - System UUID (DMI/SMBIOS data)
    - Network MAC (physical, permanent)
    - Disk Physical Serial (physical drive)
    - BIOS Serial/UUID (physical hardware)
    """
    
    def __init__(self, debug=False):
        self.app_name = "KOKONUT"
        self.debug = debug
        self.id_file = self._get_id_file_path()
        self.machine_id = None
        
    def _log_debug(self, msg):
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[DEBUG] {msg}")
    
    def _get_id_file_path(self):
        """Get the path for the machine ID file."""
        if platform.system() == 'Windows':
            app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
            app_dir = os.path.join(app_data, self.app_name)
        else:
            home = os.path.expanduser('~')
            app_dir = os.path.join(home, '.config', self.app_name.lower())
        
        Path(app_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(app_dir, 'machine_id.json')
    
    def _get_system_name(self):
        """Get accurate system name for display purposes only."""
        system = platform.system()
        
        if system == 'Windows':
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                product_name = winreg.QueryValueEx(key, "ProductName")[0]
                current_build = winreg.QueryValueEx(key, "CurrentBuild")[0]
                ubr = winreg.QueryValueEx(key, "UBR")[0]
                
                build_num = int(current_build) if current_build.isdigit() else 0
                if build_num >= 22000 and "Windows 10" in product_name:
                    product_name = product_name.replace("Windows 10", "Windows 11")
                
                return f"{product_name} (Build {current_build}.{ubr})"
            except:
                return f"Windows {platform.release()}"
        elif system == 'Linux':
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            return line.split('=')[1].strip('"\n')
            except:
                pass
            return "Linux"
        elif system == 'Darwin':
            try:
                import subprocess
                result = subprocess.run(['sw_vers', '-productVersion'], 
                                      capture_output=True, text=True)
                if result.stdout:
                    return f"macOS {result.stdout.strip()}"
            except:
                pass
            return "macOS"
        else:
            return system or "Unknown"
    
    def _get_cpu_id(self):
        """Get CPU ID/Serial - PERMANENT (built into CPU)."""
        try:
            if platform.system() == 'Windows':
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                try:
                    processor_id = winreg.QueryValueEx(key, "ProcessorId")[0]
                    if processor_id and processor_id != '0000000000000000':
                        return f"cpu_{processor_id}"
                except:
                    pass
                
                # Fallback using WMIC
                try:
                    import subprocess
                    result = subprocess.run(['wmic', 'cpu', 'get', 'ProcessorId'], 
                                          capture_output=True, text=True)
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        cpu_id = lines[1].strip()
                        if cpu_id and cpu_id != '0000000000000000':
                            return f"cpu_{cpu_id}"
                except:
                    pass
            
            elif platform.system() == 'Linux':
                # Try /proc/cpuinfo for CPU serial
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('Serial'):
                                serial = line.split(':')[1].strip()
                                if serial and serial != '0000000000000000':
                                    return f"cpu_{serial}"
                except:
                    pass
                
                # Try dmidecode for CPU ID
                try:
                    import subprocess
                    result = subprocess.run(['dmidecode', '-t', 'processor', '|', 'grep', 'ID'], 
                                          shell=True, capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'ID' in line:
                            cpu_id = line.split(':')[1].strip()
                            if cpu_id and cpu_id != 'Not Specified':
                                return f"cpu_{cpu_id}"
                except:
                    pass
            
            elif platform.system() == 'Darwin':
                # macOS: Use hardware UUID (permanent)
                try:
                    import subprocess
                    result = subprocess.run(['ioreg', '-l', '|', 'grep', 'IOPlatformUUID'], 
                                          shell=True, capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'IOPlatformUUID' in line:
                            uuid_val = line.split('"')[1] if '"' in line else line.split('=')[1].strip()
                            if uuid_val:
                                return f"cpu_{uuid_val.replace('-', '')}"
                except:
                    pass
        except Exception as e:
            self._log_debug(f"CPU ID failed: {e}")
        
        return None
    
    def _get_motherboard_serial(self):
        """Get Motherboard Serial - PERMANENT (physical hardware)."""
        try:
            if platform.system() == 'Windows':
                try:
                    import subprocess
                    result = subprocess.run(['wmic', 'baseboard', 'get', 'SerialNumber'], 
                                          capture_output=True, text=True)
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        serial = lines[1].strip()
                        if serial and serial not in ['SerialNumber', 'To be filled by O.E.M.', 'Not Available']:
                            return f"mb_{serial}"
                except:
                    pass
            
            elif platform.system() == 'Linux':
                # Try /sys/class/dmi/id/board_serial
                try:
                    with open('/sys/class/dmi/id/board_serial', 'r') as f:
                        serial = f.read().strip()
                        if serial and serial not in ['Not Specified', 'Serial Number', 'Not Available']:
                            return f"mb_{serial}"
                except:
                    pass
                
                # Try dmidecode
                try:
                    import subprocess
                    result = subprocess.run(['dmidecode', '-t', 'baseboard', '|', 'grep', 'Serial Number'], 
                                          shell=True, capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'Serial Number' in line:
                            serial = line.split(':')[1].strip()
                            if serial and serial not in ['Not Specified', 'Serial Number', 'Not Available']:
                                return f"mb_{serial}"
                except:
                    pass
            
            elif platform.system() == 'Darwin':
                # macOS: Use hardware serial
                try:
                    import subprocess
                    result = subprocess.run(['system_profiler', 'SPHardwareDataType', '|', 'grep', 'Serial Number'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'Serial Number' in line:
                            serial = line.split(':')[1].strip()
                            if serial:
                                return f"mb_{serial}"
                except:
                    pass
        except Exception as e:
            self._log_debug(f"Motherboard serial failed: {e}")
        
        return None
    
    def _get_system_uuid(self):
        """Get System UUID - PERMANENT (DMI/SMBIOS data)."""
        try:
            if platform.system() == 'Windows':
                # Use MachineGuid (permanent system identifier)
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Cryptography")
                machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                if machine_guid:
                    return f"system_{machine_guid}"
            
            elif platform.system() == 'Linux':
                # Try /sys/class/dmi/id/product_uuid
                try:
                    with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                        uuid_val = f.read().strip()
                        if uuid_val and uuid_val not in ['Not Specified', 'Not Available']:
                            return f"system_{uuid_val}"
                except:
                    pass
                
                # Try /sys/class/dmi/id/board_serial as fallback
                try:
                    with open('/sys/class/dmi/id/board_serial', 'r') as f:
                        serial = f.read().strip()
                        if serial and serial not in ['Not Specified', 'Serial Number', 'Not Available']:
                            return f"system_{serial}"
                except:
                    pass
            
            elif platform.system() == 'Darwin':
                # macOS: Use IOPlatformUUID
                try:
                    import subprocess
                    result = subprocess.run(['ioreg', '-l', '|', 'grep', 'IOPlatformUUID'], 
                                          shell=True, capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'IOPlatformUUID' in line:
                            uuid_val = line.split('"')[1] if '"' in line else line.split('=')[1].strip()
                            if uuid_val:
                                return f"system_{uuid_val.replace('-', '')}"
                except:
                    pass
        except Exception as e:
            self._log_debug(f"System UUID failed: {e}")
        
        return None
    
    def _get_mac_addresses(self):
        """Get physical MAC addresses - PERMANENT (hardware level)."""
        macs = []
        
        try:
            # Method 1: Primary MAC via uuid.getnode()
            mac = uuid.getnode()
            if mac and mac != 0xFFFFFFFFFFFF:
                mac_str = f"{mac:012x}"
                if mac_str != "ffffffffffff":
                    macs.append(f"mac_{mac_str}")
                    self._log_debug(f"Found MAC (uuid): {mac_str}")
        except:
            pass
        
        # Method 2: All network interfaces
        try:
            import netifaces
            # Skip virtual interfaces
            skip_ifaces = ['lo', 'docker', 'veth', 'br-', 'virbr', 'tun', 'tap']
            
            for iface in netifaces.interfaces():
                # Skip virtual/loopback interfaces
                if any(iface.startswith(skip) for skip in skip_ifaces):
                    continue
                
                try:
                    iface_data = netifaces.ifaddresses(iface)
                    if netifaces.AF_LINK in iface_data:
                        for addr in iface_data[netifaces.AF_LINK]:
                            mac = addr.get('addr')
                            if mac:
                                clean_mac = mac.replace(':', '').replace('-', '').lower()
                                if (clean_mac and 
                                    clean_mac != '000000000000' and 
                                    len(clean_mac) == 12 and
                                    clean_mac != 'ffffffffffff'):
                                    macs.append(f"mac_{clean_mac}")
                                    self._log_debug(f"Found MAC: {clean_mac} on {iface}")
                except:
                    continue
        except ImportError:
            # Fallback methods
            if platform.system() == 'Linux':
                try:
                    import glob
                    skip_ifaces = ['lo', 'docker', 'veth', 'br-', 'virbr']
                    for path in glob.glob('/sys/class/net/*/address'):
                        iface_name = path.split('/')[-2]
                        if any(iface_name.startswith(skip) for skip in skip_ifaces):
                            continue
                        
                        try:
                            with open(path, 'r') as f:
                                mac = f.read().strip()
                                if mac:
                                    clean_mac = mac.replace(':', '').lower()
                                    if (clean_mac and 
                                        clean_mac != '000000000000' and 
                                        len(clean_mac) == 12 and
                                        clean_mac != 'ffffffffffff'):
                                        macs.append(f"mac_{clean_mac}")
                        except:
                            continue
                except:
                    pass
            
            elif platform.system() == 'Windows':
                try:
                    import subprocess
                    result = subprocess.run(['getmac', '/FO', 'CSV', '/NH'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.strip('"').split('","')
                            if len(parts) >= 2:
                                mac = parts[0].replace('-', '').lower()
                                # Skip virtual adapters
                                if (mac and 
                                    mac != '000000000000' and 
                                    len(mac) == 12 and
                                    mac != 'ffffffffffff' and
                                    not parts[1].lower().startswith('virtual')):
                                    macs.append(f"mac_{mac}")
                except:
                    pass
        
        # Remove duplicates
        seen = set()
        unique_macs = []
        for mac in macs:
            if mac not in seen:
                seen.add(mac)
                unique_macs.append(mac)
        
        self._log_debug(f"Found {len(unique_macs)} physical MAC addresses")
        return unique_macs
    
    def _get_disk_serials(self):
        """Get physical disk serial numbers - PERMANENT (hardware)."""
        serials = []
        
        try:
            if platform.system() == 'Windows':
                # Get physical disk serials (NOT volume serials)
                try:
                    import subprocess
                    result = subprocess.run(['wmic', 'diskdrive', 'get', 'SerialNumber'], 
                                          capture_output=True, text=True)
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:
                        serial = line.strip()
                        if serial and serial not in ['SerialNumber', 'None', '']:
                            serials.append(f"disk_{serial}")
                except:
                    pass
                
                # PowerShell alternative
                try:
                    import subprocess
                    result = subprocess.run([
                        'powershell', '-Command',
                        'Get-PhysicalDisk | Where-Object {$_.SerialNumber} | Select-Object -ExpandProperty SerialNumber'
                    ], capture_output=True, text=True)
                    for line in result.stdout.strip().split('\n'):
                        serial = line.strip()
                        if serial and serial not in ['SerialNumber', 'None', '']:
                            serials.append(f"disk_{serial}")
                except:
                    pass
            
            elif platform.system() == 'Linux':
                # Get disk serials from /dev/disk/by-id
                try:
                    import glob
                    for path in glob.glob('/dev/disk/by-id/*'):
                        basename = os.path.basename(path)
                        # Skip partitions and device mapper
                        if (not basename.startswith('dm-') and 
                            not basename.endswith('-part') and
                            not basename.startswith('wwn-0x')):
                            # Extract serial from the ID
                            if 'ata-' in basename:
                                serial = basename.replace('ata-', '')
                            elif 'scsi-' in basename:
                                serial = basename.replace('scsi-', '')
                            elif 'nvme-' in basename:
                                serial = basename.replace('nvme-', '')
                            else:
                                continue
                            
                            if serial:
                                serials.append(f"disk_{serial}")
                except:
                    pass
                
                # lsblk alternative
                try:
                    import subprocess
                    result = subprocess.run(['lsblk', '-o', 'SERIAL', '-n'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.strip().split('\n'):
                        serial = line.strip()
                        if serial and serial not in ['SerialNumber', 'None', '']:
                            serials.append(f"disk_{serial}")
                except:
                    pass
            
            elif platform.system() == 'Darwin':
                # macOS: Get disk serials
                try:
                    import subprocess
                    result = subprocess.run(['system_profiler', 'SPStorageDataType', '|', 'grep', 'Serial Number'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'Serial Number:' in line:
                            serial = line.split(':')[1].strip()
                            if serial:
                                serials.append(f"disk_{serial}")
                except:
                    pass
        except Exception as e:
            self._log_debug(f"Disk serial collection failed: {e}")
        
        # Remove duplicates
        serials = list(set(serials))
        self._log_debug(f"Found {len(serials)} physical disk serials")
        return serials
    
    def _get_bios_serial(self):
        """Get BIOS Serial/UUID - PERMANENT (physical hardware)."""
        try:
            if platform.system() == 'Windows':
                try:
                    import subprocess
                    result = subprocess.run(['wmic', 'bios', 'get', 'SerialNumber'], 
                                          capture_output=True, text=True)
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        serial = lines[1].strip()
                        if serial and serial not in ['SerialNumber', 'None', '']:
                            return f"bios_{serial}"
                except:
                    pass
            
            elif platform.system() == 'Linux':
                # Try /sys/class/dmi/id/bios_version
                try:
                    with open('/sys/class/dmi/id/bios_version', 'r') as f:
                        version = f.read().strip()
                        if version and version not in ['Not Specified', 'Not Available']:
                            # Add date for uniqueness
                            try:
                                with open('/sys/class/dmi/id/bios_date', 'r') as df:
                                    date = df.read().strip()
                                    if date:
                                        return f"bios_{version}_{date}"
                            except:
                                pass
                            return f"bios_{version}"
                except:
                    pass
                
                # Try dmidecode
                try:
                    import subprocess
                    result = subprocess.run(['dmidecode', '-t', 'bios', '|', 'grep', -E, 'Version|Release Date'], 
                                          shell=True, capture_output=True, text=True)
                    version = ''
                    date = ''
                    for line in result.stdout.split('\n'):
                        if 'Version' in line:
                            version = line.split(':')[1].strip()
                        elif 'Release Date' in line:
                            date = line.split(':')[1].strip()
                    
                    if version and version not in ['Not Specified', 'Not Available']:
                        if date:
                            return f"bios_{version}_{date}"
                        return f"bios_{version}"
                except:
                    pass
            
            elif platform.system() == 'Darwin':
                # macOS: Get boot ROM version (permanent)
                try:
                    import subprocess
                    result = subprocess.run(['system_profiler', 'SPHardwareDataType', '|', 'grep', 'Boot ROM'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'Boot ROM' in line:
                            version = line.split(':')[1].strip()
                            if version:
                                return f"bios_{version}"
                except:
                    pass
        except Exception as e:
            self._log_debug(f"BIOS serial failed: {e}")
        
        return None
    
    def _get_permanent_hardware_ids(self):
        """
        Collect ONLY truly permanent hardware identifiers.
        
        Permanent identifiers:
        - CPU ID/Serial (built into CPU)
        - Motherboard Serial (physical hardware)
        - System UUID (DMI/SMBIOS data)
        - Network MAC (physical, permanent)
        - Disk Physical Serial (physical drive)
        - BIOS Serial/UUID (physical hardware)
        """
        hardware_ids = []
        
        self._log_debug("Collecting permanent hardware identifiers...")
        self._log_debug("=" * 40)
        
        # 1. CPU ID (built into CPU)
        cpu_id = self._get_cpu_id()
        if cpu_id:
            hardware_ids.append(cpu_id)
            self._log_debug(f"✓ CPU ID: {cpu_id}")
        else:
            self._log_debug("✗ CPU ID: Not found")
        
        # 2. Motherboard Serial (physical hardware)
        mb_serial = self._get_motherboard_serial()
        if mb_serial:
            hardware_ids.append(mb_serial)
            self._log_debug(f"✓ Motherboard Serial: {mb_serial}")
        else:
            self._log_debug("✗ Motherboard Serial: Not found")
        
        # 3. System UUID (DMI/SMBIOS)
        system_uuid = self._get_system_uuid()
        if system_uuid:
            hardware_ids.append(system_uuid)
            self._log_debug(f"✓ System UUID: {system_uuid}")
        else:
            self._log_debug("✗ System UUID: Not found")
        
        # 4. MAC Addresses (physical, permanent)
        macs = self._get_mac_addresses()
        if macs:
            hardware_ids.extend(macs)
            self._log_debug(f"✓ MAC Addresses: {len(macs)} found")
        else:
            self._log_debug("✗ MAC Addresses: None found")
        
        # 5. Disk Physical Serials (physical drives)
        disk_serials = self._get_disk_serials()
        if disk_serials:
            hardware_ids.extend(disk_serials)
            self._log_debug(f"✓ Disk Serials: {len(disk_serials)} found")
        else:
            self._log_debug("✗ Disk Serials: None found")
        
        # 6. BIOS Serial/UUID (physical hardware)
        bios_serial = self._get_bios_serial()
        if bios_serial:
            hardware_ids.append(bios_serial)
            self._log_debug(f"✓ BIOS Serial: {bios_serial}")
        else:
            self._log_debug("✗ BIOS Serial: Not found")
        
        self._log_debug("=" * 40)
        self._log_debug(f"Total permanent IDs collected: {len(hardware_ids)}")
        
        return hardware_ids
    
    def generate_machine_id(self):
        """Generate or retrieve a persistent machine ID."""
        # Try to read existing ID from file
        if os.path.exists(self.id_file):
            try:
                with open(self.id_file, 'r') as f:
                    data = json.load(f)
                    if data.get('machine_id'):
                        self.machine_id = data['machine_id']
                        self._log_debug(f"Loaded existing ID: {self.machine_id}")
                        return self.machine_id
            except (json.JSONDecodeError, IOError) as e:
                self._log_debug(f"Failed to read existing ID: {e}")
        
        # Generate a new ID from permanent hardware identifiers
        self._log_debug("Generating new machine ID from permanent hardware...")
        hardware_ids = self._get_permanent_hardware_ids()
        
        if not hardware_ids:
            self._log_debug("ERROR: No hardware identifiers found!")
            # In the extremely rare case of no hardware IDs, use hostname + MAC
            # This should never happen on real hardware
            fallback = f"host_{socket.gethostname()}_uuid_{str(uuid.uuid4())}"
            hardware_ids.append(f"fallback_{hashlib.sha256(fallback.encode()).hexdigest()}")
            self._log_debug("WARNING: Using fallback identifier!")
        
        # Create fingerprint from ALL hardware IDs
        # Sort to ensure consistent ordering
        fingerprint = '|'.join(sorted(hardware_ids))
        
        # Add version identifier for future compatibility
        versioned_fingerprint = f"v3|{fingerprint}"
        
        self.machine_id = hashlib.sha256(versioned_fingerprint.encode()).hexdigest()[:16]
        self._log_debug(f"Generated machine ID: {self.machine_id}")
        
        # Save the ID with metadata
        try:
            with open(self.id_file, 'w') as f:
                json.dump({
                    'machine_id': self.machine_id,
                    'version': 3,
                    'generated_at': platform.node(),
                    'platform': self._get_system_name(),
                    'hardware_ids_used': hardware_ids,
                    'hardware_count': len(hardware_ids),
                    'mac_count': sum(1 for hw in hardware_ids if hw.startswith('mac_')),
                    'disk_count': sum(1 for hw in hardware_ids if hw.startswith('disk_'))
                }, f, indent=2)
            self._log_debug(f"Saved ID to: {self.id_file}")
        except IOError as e:
            self._log_debug(f"Failed to save ID: {e}")
        
        return self.machine_id
    
    def get_id(self):
        """Return the machine ID, generating if necessary."""
        if not self.machine_id:
            self.generate_machine_id()
        return self.machine_id
    
    def verify_consistency(self):
        """Verify that the machine ID is still consistent with the current system."""
        if not self.machine_id:
            return False
        
        # Get current hardware IDs
        hardware_ids = self._get_permanent_hardware_ids()
        
        if not hardware_ids:
            return False
        
        # Generate ID with same method
        fingerprint = '|'.join(sorted(hardware_ids))
        versioned_fingerprint = f"v3|{fingerprint}"
        new_id = hashlib.sha256(versioned_fingerprint.encode()).hexdigest()[:16]
        
        is_consistent = self.machine_id == new_id
        if not is_consistent:
            self._log_debug(f"Consistency check failed!")
            self._log_debug(f"  Old ID: {self.machine_id}")
            self._log_debug(f"  New ID: {new_id}")
        
        return is_consistent
    
    def get_machine_info(self):
        """Get detailed machine information."""
        info = {
            'machine_id': self.get_id(),
            'system': self._get_system_name(),
            'system_raw': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'hostname': platform.node(),
            'python_version': sys.version.split()[0],
        }
        
        # Add stored metadata if available
        if os.path.exists(self.id_file):
            try:
                with open(self.id_file, 'r') as f:
                    data = json.load(f)
                    info['id_version'] = data.get('version', 1)
                    info['hardware_count'] = data.get('hardware_count', 0)
                    info['mac_count'] = data.get('mac_count', 0)
                    info['disk_count'] = data.get('disk_count', 0)
            except:
                pass
        
        return info
    
    def print_system_info(self):
        """Print detailed system information for debugging."""
        info = self.get_machine_info()
        print("\n" + "=" * 60)
        print("SYSTEM INFORMATION")
        print("=" * 60)
        for key, value in info.items():
            print(f"{key:25}: {value}")
        print("=" * 60)
        
        # Verify consistency
        is_consistent = self.verify_consistency()
        print(f"\nID Consistency Check: {'✓ PASSED' if is_consistent else '✗ FAILED'}")
        print("=" * 60)
        
        # Show hardware IDs used
        if os.path.exists(self.id_file):
            try:
                with open(self.id_file, 'r') as f:
                    data = json.load(f)
                    hardware_ids = data.get('hardware_ids_used', [])
                    if hardware_ids:
                        print("\nHardware Identifiers Used:")
                        print("-" * 40)
                        for hw in sorted(hardware_ids):
                            print(f"  {hw[:30]}...")
                        print("=" * 60)
            except:
                pass


# Create a singleton instance
_machine_id_instance = None

def get_machine_id(debug=False):
    """Get the machine ID singleton instance."""
    global _machine_id_instance
    if _machine_id_instance is None:
        _machine_id_instance = MachineID(debug=debug)
    return _machine_id_instance.get_id()

def get_machine_info(debug=False):
    """Get machine information."""
    global _machine_id_instance
    if _machine_id_instance is None:
        _machine_id_instance = MachineID(debug=debug)
    return _machine_id_instance.get_machine_info()

def verify_machine_id(debug=False):
    """Verify the machine ID consistency."""
    global _machine_id_instance
    if _machine_id_instance is None:
        _machine_id_instance = MachineID(debug=debug)
    return _machine_id_instance.verify_consistency()

def print_system_info(debug=False):
    """Print detailed system information."""
    global _machine_id_instance
    if _machine_id_instance is None:
        _machine_id_instance = MachineID(debug=debug)
    _machine_id_instance.print_system_info()


if __name__ == "__main__":
    print_system_info(debug=True)