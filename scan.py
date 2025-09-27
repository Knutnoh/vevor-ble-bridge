from bluepy.btle import Scanner, DefaultDelegate, BTLEDisconnectError
import os
import time

HEATER_MAC = os.environ.get("BLE_MAC_ADDRESS", "ec:b1:c3:00:3c:56").lower()

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        super().__init__()

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if dev.addr.lower() == HEATER_MAC:
            if isNewDev:
                print(f"[SCAN] Discovered heater {dev.addr} (RSSI={dev.rssi} dB)")
            elif isNewData:
                print(f"[SCAN] Updated data from heater {dev.addr} (RSSI={dev.rssi} dB)")

print("[SCAN] Creating scanner...")
scanner = Scanner().withDelegate(ScanDelegate())
scan_time = float(os.environ.get("SCAN_TIME", 10.0))
print(f"[SCAN] Scanning for heater for {scan_time} seconds...")

try:
    devices = scanner.scan(scan_time)
except BTLEDisconnectError as e:
    print(f"[SCAN] Scan finished with BTLEDisconnectError: {e}")
except Exception as e:
    print(f"[SCAN] Scan finished with exception: {e}")

print("[SCAN] Finished scanning.\n")

for dev in devices:
    if dev.addr.lower() == HEATER_MAC:
        print(f"[SCAN] Device {dev.addr} ({dev.addrType}), RSSI={dev.rssi} dB")
        for adtype, desc, value in dev.getScanData():
            print(f"[SCAN] {desc} = {value}")
