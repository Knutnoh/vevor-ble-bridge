# Vevor BLE Bridge (angepasst)
# 2025 Dein Setup

import paho.mqtt.client as mqtt
import logging
import platform
import json
import time
import vevor
import os
import sys

# ===== Configuration =====
ble_mac_address = os.environ["BLE_MAC_ADDRESS"]
ble_passkey = int(os.environ.get("BLE_PASSKEY", 1234))
ble_poll_interval = int(os.environ.get("BLE_POLL_INTERVAL", 2))

device_name = os.environ["DEVICE_NAME"]
device_manufacturer = os.environ.get("DEVICE_MANUFACTURER", "Vevor")
device_model = os.environ["DEVICE_MODEL"]
device_id = "BYD-" + ble_mac_address.replace(":", "").upper()
via_device = platform.uname()[1]

mqtt_host = os.environ.get("MQTT_HOST", "127.0.0.1")
mqtt_username = os.environ.get("MQTT_USERNAME")
mqtt_password = os.environ.get("MQTT_PASSWORD")
mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
mqtt_discovery_prefix = os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant")
mqtt_prefix = f"{os.environ.get('MQTT_PREFIX', '').rstrip('/')}/{device_id}"

run = True
modes = ["Power Level", "Temperature"]

# ===== Logger =====
def init_logger():
    logger = logging.getLogger("vevor-ble-bridge")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S %z"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

logger = init_logger()

# ===== MQTT Client =====
def on_connect(client, userdata, flags, rc):
    global run
    if rc:
        run = False
        raise RuntimeError(f"Cannot connect to MQTT broker (error {rc})")
    logger.info(f"Connected to MQTT broker")
    client.subscribe([
        (f"{mqtt_prefix}/start/cmd", 2),
        (f"{mqtt_prefix}/stop/cmd", 2),
        (f"{mqtt_prefix}/level/cmd", 2),
        (f"{mqtt_prefix}/temperature/cmd", 2),
        (f"{mqtt_prefix}/mode/cmd", 2),
    ])
    publish_ha_config()

def on_message(client, userdata, msg):
    logger.debug(f"Received MQTT message: {msg.topic} -> {msg.payload}")
    if msg.topic == f"{mqtt_prefix}/start/cmd":
        logger.info("Received START command")
        dispatch_result(vdh.start())
    elif msg.topic == f"{mqtt_prefix}/stop/cmd":
        logger.info("Received STOP command")
        dispatch_result(vdh.stop())
    elif msg.topic == f"{mqtt_prefix}/level/cmd":
        logger.info(f"Received LEVEL={int(msg.payload)} command")
        dispatch_result(vdh.set_level(int(msg.payload)))
    elif msg.topic == f"{mqtt_prefix}/temperature/cmd":
        logger.info(f"Received TEMPERATURE={int(msg.payload)} command")
        dispatch_result(vdh.set_temperature(int(msg.payload)))
    elif msg.topic == f"{mqtt_prefix}/mode/cmd":
        logger.info(f"Received MODE={msg.payload} command")
        dispatch_result(vdh.set_mode(modes.index(msg.payload.decode('ascii')) + 1))

def init_client():
    client = mqtt.Client(client_id=device_id, clean_session=True)
    if mqtt_username and mqtt_password:
        logger.info(f"Connecting to MQTT broker {mqtt_username}@{mqtt_host}:{mqtt_port}")
        client.username_pw_set(mqtt_username, mqtt_password)
    else:
        logger.info(f"Connecting to MQTT broker {mqtt_host}:{mqtt_port}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_host, mqtt_port)
    return client

client = init_client()

# ===== HA MQTT Discovery =====
def get_device_conf():
    return {
        "name": device_name,
        "identifiers": device_id,
        "manufacturer": device_manufacturer,
        "model": device_model,
        "via_device": via_device,
        "sw": "Vevor-BLE-Bridge",
    }

def publish_ha_config():
    # Buttons, sensors, numbers, select – hier analog wie zuvor
    # Für Kürze hier gekürzt, kann vollständig aus deinem alten main.py übernommen werden
    pass

# ===== Dispatcher =====
def dispatch_result(result):
    stop_pub = start_pub = level_pub = temperature_pub = mode_pub = False
    if result:
        logger.debug(f"[DEBUG] Notification: {result.data()}")
        msg = result.running_step_msg
        if result.error:
            msg = f"{msg} ({result.error_msg})"
        client.publish(f"{mqtt_prefix}/status/state", msg)
        client.publish(f"{mqtt_prefix}/room_temperature/state", result.cab_temperature)
        if result.running_mode:
            client.publish(f"{mqtt_prefix}/mode/av", "online")
            client.publish(f"{mqtt_prefix}/mode/state", modes[result.running_mode - 1])
            mode_pub = True
        if result.running_step:
            client.publish(f"{mqtt_prefix}/voltage/state", result.supply_voltage)
            client.publish(f"{mqtt_prefix}/altitude/state", result.altitude)
            client.publish(f"{mqtt_prefix}/heater_temperature/state", result.case_temperature)
            client.publish(f"{mqtt_prefix}/level/state", result.set_level)
            if result.set_temperature is not None:
                client.publish(f"{mqtt_prefix}/temperature/state", result.set_temperature)
            if ((result.running_mode == 0) or (result.running_mode == 1)) and (result.running_step < 4):
                client.publish(f"{mqtt_prefix}/level/av", "online")
                level_pub = True
            if result.running_mode == 2:
                client.publish(f"{mqtt_prefix}/temperature/av", "online")
                temperature_pub = True
            if (result.running_step > 0) and (result.running_step < 4):
                client.publish(f"{mqtt_prefix}/stop/av", "online")
                stop_pub = True
        else:
            client.publish(f"{mqtt_prefix}/start/av", "online")
            start_pub = True
    if not stop_pub:
        client.publish(f"{mqtt_prefix}/stop/av", "offline")
    if not start_pub:
        client.publish(f"{mqtt_prefix}/start/av", "offline")
    if not level_pub:
        client.publish(f"{mqtt_prefix}/level/av", "offline")
    if not temperature_pub:
        client.publish(f"{mqtt_prefix}/temperature/av", "offline")
    if not mode_pub:
        client.publish(f"{mqtt_prefix}/mode/av", "offline")

# ===== Initialize BLE Heater =====
vdh = vevor.DieselHeater(ble_mac_address, ble_passkey)

# Debug BLE Services & Characteristics
print(f"[DEBUG] Verbunden mit BLE-Gerät: {vdh.mac_address}")
for svc in vdh.peripheral.getServices():
    print(f"[DEBUG] Service UUID: {svc.uuid}")
    for ch in svc.getCharacteristics():
        props = ch.propertiesToString()
        print(f"[DEBUG] Char UUID: {ch.uuid}  Properties: {props}  Handle: {ch.getHandle()}")

# ===== Start MQTT loop =====
client.loop_start()

# ===== Main Polling Loop =====
while run:
    result = vdh.get_status()
    if not result:
        print("[DEBUG] Keine Notification erhalten")
    dispatch_result(result)
    time.sleep(ble_poll_interval)
