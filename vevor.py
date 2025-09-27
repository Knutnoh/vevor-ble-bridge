# Vevor BLE Bridge (angepasst für EC:B1:C3:00:3C:56)
# 2025 Anpassung für custom BLE Heater
import os
from bluepy.btle import Peripheral, DefaultDelegate
import time
import random
import math
import paho.mqtt.client as mqtt

# Hilfsfunktionen
def _u8tonumber(e):
    return (e + 256) if (e < 0) else e

def _UnsignToSign(e):
    if e > 32767.5:
        e = e | -65536
    return e

# Notification Parsing
class _DieselHeaterNotification:
    _error_strings = (
        "No fault", "Startup failure", "Lack of fuel", "Supply voltage overrun",
        "Outlet sensor fault", "Inlet sensor fault", "Pulse pump fault", "Fan fault",
        "Ignition unit fault", "Overheating", "Overheat sensor fault"
    )
    _running_step_strings = ("Standby", "Self-test", "Ignition", "Running", "Cooldown")

    def __init__(self, data):
        fb, sb = _u8tonumber(data[0]), _u8tonumber(data[1])
        self.raw = data
        self.running_state = _u8tonumber(data[3])
        self.error = _u8tonumber(data[4])
        self.error_msg = self._error_strings[self.error] if self.error < len(self._error_strings) else "Unknown"
        self.running_step = _u8tonumber(data[5])
        self.running_step_msg = self._running_step_strings[self.running_step] if self.running_step < len(self._running_step_strings) else "Unknown"

    def data(self):
        return vars(self)

# BLE Delegate
class _DieselHeaterDelegate(DefaultDelegate):
    def __init__(self, parent):
        self.parent = parent

    def handleNotification(self, cHandle, data):
        self.parent._last_notification = _DieselHeaterNotification(data)
        print(f"[DEBUG] Notification received: {self.parent._last_notification.data()}")

# DieselHeater Class für custom UUIDs
class DieselHeater:
    _service_uuid = "0000fff0-0000-1000-8000-00805f9b34fb"
    _char_notify_uuid = "0000fff2-0000-1000-8000-00805f9b34fb"
    _char_write_uuid  = "0000fff1-0000-1000-8000-00805f9b34fb"
    _last_notification = None

    def __init__(self, mac_address: str, passkey: int):
        self.mac_address = mac_address
        self.passkey = passkey
        print(f"[DEBUG] Verbinde mit BLE-Gerät {mac_address}")
        self.peripheral = Peripheral(mac_address, "public")
        self.service = self.peripheral.getServiceByUUID(self._service_uuid)
        self.characteristic_notify = self.service.getCharacteristics(self._char_notify_uuid)[0]
        self.characteristic_write  = self.service.getCharacteristics(self._char_write_uuid)[0]
        self.peripheral.setDelegate(_DieselHeaterDelegate(self))
        print(f"[DEBUG] BLE-Verbindung aufgebaut. Services und Characteristics:")
        for svc in self.peripheral.getServices():
            print(f"[DEBUG] Service UUID: {svc.uuid}")
            for ch in svc.getCharacteristics():
                print(f"[DEBUG] Char UUID: {ch.uuid}, Handle: {ch.getHandle()}, Props: {ch.propertiesToString()}")

    def _send_command(self, command: int, argument: int):
        o = bytearray([0xAA, 85, math.floor(self.passkey / 100), self.passkey % 100,
                       command % 256, argument % 256, argument // 256, 0])
        o[7] = sum(o[:7]) % 256
        self._last_notification = None
        self.characteristic_write.write(o, withResponse=True)
        if self.peripheral.waitForNotifications(1):
            return self._last_notification
        return None

    def get_status(self):
        return self._send_command(1, 0)

    def start(self):
        return self._send_command(3, 1)

    def stop(self):
        return self._send_command(3, 0)

    def set_level(self, level):
        if not 1 <= level <= 36:
            raise RuntimeError("Invalid level")
        return self._send_command(4, level)

    def set_mode(self, mode):
        if mode not in (1,2):
            raise RuntimeError("Invalid mode")
        return self._send_command(2, mode)

# Hauptprogramm mit Polling und MQTT
if __name__ == "__main__":
    MAC = os.environ.get("BLE_MAC_ADDRESS", "EC:B1:C3:00:3C:56")
    PASSKEY = int(os.environ.get("BLE_PASSKEY", 1234))
    POLL_INTERVAL = 2
    MQTT_HOST = os.environ.get("MQTT_HOST", "192.168.2.155")
    MQTT_TOPIC = os.environ.get("MQTT_PREFIX", "home/ble/heater/status")

    heater = DieselHeater(MAC, PASSKEY)
    client = mqtt.Client()
    client.connect(MQTT_HOST, 1883, 60)
    print(f"[DEBUG] MQTT verbunden mit {MQTT_HOST}")

    try:
        while True:
            status = heater.get_status()
            if status:
                payload = status.raw.hex()
                client.publish(MQTT_TOPIC, payload)
                print(f"[DEBUG] MQTT-Publish: {MQTT_TOPIC} -> {payload}")
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("[DEBUG] Script beendet")
        heater.stop()
