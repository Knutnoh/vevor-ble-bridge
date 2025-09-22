from bluepy.btle import Scanner, DefaultDelegate

HEATER_MAC = "ec:b1:c3:00:3c:56"  # MAC-Adresse in Kleinbuchstaben

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if dev.addr.lower() == HEATER_MAC:
            if isNewDev:
                print(f"Discovered heater {dev.addr} (RSSI={dev.rssi} dB)")
            elif isNewData:
                print(f"Received new data from heater {dev.addr} (RSSI={dev.rssi} dB)")

print("Creating scanner...")
scanner = Scanner().withDelegate(ScanDelegate())
print("Scanning for heater...")
devices = scanner.scan(10.0)  # Scan für 10 Sekunden
print("Finished scanning.\n")

# Optional: nochmal die Details durchgehen
for dev in devices:
    if dev.addr.lower() == HEATER_MAC:
        print(f"Device {dev.addr} ({dev.addrType}), RSSI={dev.rssi} dB")
        for adtype, desc, value in dev.getScanData():
            print(f"{desc} = {value}")
