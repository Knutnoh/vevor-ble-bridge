import random
import math
import threading
from bluepy.btle import Peripheral, DefaultDelegate

def _u8tonumber(e):
    return (e + 256) if (e < 0) else e

def _UnsignToSign(e):
    if e > 32767.5:
        e = e | -65536
    return e

class _DieselHeaterNotification:
    _error_strings = (
        "No fault",
        "Startup failure",
        "Lack of fuel",
        "Supply voltage overrun",
        "Outlet sensor fault",
        "Inlet sensor fault",
        "Pulse pump fault",
        "Fan fault",
        "Ignition unit fault",
        "Overheating",
        "Overheat sensor fault",
    )
    _running_step_strings = (
        "Standby",
        "Self-test",
        "Ignition",
        "Running",
        "Cooldown",
    )

    def __init__(self, raw):
        fb, sb = _u8tonumber(raw[0]), _u8tonumber(raw[1])
        if fb != 0xAA:
            raise RuntimeError("Unrecognized payload")
        self.running_state = _u8tonumber(raw[3])
        self.error = _u8tonumber(raw[4])
        self.error_msg = self._error_strings[self.error]
        self.running_step = _u8tonumber(raw[5])
        self.running_step_msg = self._running_step_strings[self.running_step]
        self.altitude = _u8tonumber(raw[6]) + 256 * _u8tonumber(raw[7])
        self.running_mode = _u8tonumber(raw[8])
        if self.running_mode in (0, 1):
            self.set_level = _u8tonumber(raw[9])
            self.set_temperature = None
        elif self.running_mode == 2:
            self.set_temperature = _u8tonumber(raw[9])
            self.set_level = _u8tonumber(raw[10])
        else:
            raise RuntimeError("Unrecognized running mode")
        self.supply_voltage = (256 * _u8tonumber(raw[12]) + _u8tonumber(raw[11])) / 10
        self.case_temperature = _UnsignToSign(256 * raw[14] + raw[13])
        self.cab_temperature = _UnsignToSign(256 * raw[16] + raw[15])

    def data(self):
        return vars(self)


class _DieselHeaterDelegate(DefaultDelegate):
    def __init__(self, parent):
        self.parent = parent

    def handleNotification(self, cHandle, data):
        self.parent._last_notification = _DieselHeaterNotification(data)


class DieselHeater:
    _service_uuid = "0000fff0-0000-1000-8000-00805f9b34fb"
    _write_characteristic_uuid = "0000fff2-0000-1000-8000-00805f9b34fb"
    _read_characteristic_uuid = "0000fff1-0000-1000-8000-00805f9b34fb"
    _ble_lock = threading.Lock()

   def __init__(self, mac_address: str, passkey: int):
        self._lock = threading.Lock()
        self._last_notification = None
        self.peripheral = Peripheral(mac_address, "public")
        self.peripheral.setDelegate(_DieselHeaterDelegate(self))
        # Notifications aktivieren
        self.peripheral.writeCharacteristic(
            self.read_characteristic.getHandle() + 1, b'\x01\x00', withResponse=True
        )

    def _send_command(self, command: int, argument: int, n: int):
        o = bytearray([0xAA, n % 256, 0, 0, 0, 0, 0, 0])
        if n == 136:
            o[2] = random.randint(0, 255)
            o[3] = random.randint(0, 255)
        else:
            o[2] = math.floor(self.passkey / 100)
            o[3] = self.passkey % 100
        o[4] = command % 256
        o[5] = argument % 256
        o[6] = math.floor(argument / 256)
        o[7] = o[2] + o[3] + o[4] + o[5] + o[6]

        with DieselHeater._ble_lock:
            self._last_notification = None
            self.write_characteristic.write(o, withResponse=True)
            if self.peripheral.waitForNotifications(1) and self._last_notification:
                return self._last_notification
        return None

    def get_status(self):
        with DieselHeater._ble_lock:
            if self.peripheral.waitForNotifications(1) and self._last_notification:
                return self._last_notification
            try:
                raw = self.read_characteristic.read()
                if raw:
                    self._last_notification = _DieselHeaterNotification(raw)
                    return self._last_notification
            except Exception as e:
                print(f"Fehler beim Lesen der Characteristic: {e}")
        return None
               
    def start(self):
        return self._send_command(3, 1, 85)

    def stop(self):
        return self._send_command(3, 0, 85)

    def set_level(self, level):
        if not (1 <= level <= 36):
            raise RuntimeError("Invalid level")
        return self._send_command(4, level, 85)

    def set_mode(self, mode):
        if not (1 <= mode <= 2):
            raise RuntimeError("Invalid mode")
        return self._send_command(2, mode, 85)
