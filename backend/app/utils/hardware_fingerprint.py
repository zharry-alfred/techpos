import hashlib
import platform
import uuid
import subprocess
import os

def get_hardware_fingerprint() -> str:
    """Generate a deterministic, tamper-resistant hardware fingerprint
    combining CPU identifier, system UUID, and network MAC address.
    """
    components = []
    
    # 1. System Node / MAC Address
    node = uuid.getnode()
    components.append(f"MAC:{hex(node)}")
    
    # 2. System Architecture & Machine ID
    components.append(f"PLATFORM:{platform.system()}-{platform.machine()}-{platform.processor()}")
    
    # 3. OS-Specific Hardware Identification
    try:
        if platform.system() == "Windows":
            # Query Windows machine GUID or CPU processor id via registry or powershell/wmic
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                    components.append(f"WIN_GUID:{guid}")
            except Exception:
                pass
        elif platform.system() == "Linux":
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    components.append(f"LINUX_ID:{f.read().strip()}")
        elif platform.system() == "Darwin":
            try:
                out = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]).decode()
                for line in out.splitlines():
                    if "IOPlatformUUID" in line:
                        components.append(f"MAC_UUID:{line.split('=')[-1].strip().replace('\"', '')}")
            except Exception:
                pass
    except Exception:
        pass

    raw_signature = "|".join(components)
    sha_hash = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest().upper()
    # Format into standard 4-block license key format: HW-XXXX-XXXX-XXXX-XXXX
    formatted = f"HW-{sha_hash[0:4]}-{sha_hash[4:8]}-{sha_hash[8:12]}-{sha_hash[12:16]}"
    return formatted
