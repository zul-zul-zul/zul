# main.py - SEKATA Bioflok Monitoring System
# Version: beta v0.0.12b

import network
import urequests
import utime
import machine
import _thread
import os
import gc
from machine import Pin

# --- CONFIGURATION ---
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8 in seconds
VERSION = "beta v0.0.12b"
UPDATE_FLAG_FILE = "update.flag"

# --- GLOBALS ---
monitoring_enabled = True
sensor_mode = "real"
digital_pin = Pin(15, Pin.IN)
onboard_led = Pin("LED", Pin.OUT)
internet_connected = False
stop_all_tasks = False

# --- WIFI ---
def connect_wifi():
    global internet_connected
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                internet_connected = True
                onboard_led.on()
                print("WiFi connected to", ssid)
                return True
            utime.sleep(1)
    internet_connected = False
    onboard_led.off()
    return False

# --- TIME ---
def sync_time():
    import ntptime
    ntptime.host = "pool.ntp.org"
    for _ in range(5):
        try:
            ntptime.settime()
            print("Time synchronized via NTP")
            return True
        except:
            utime.sleep(10)
    return False

def get_time():
    t = utime.time() + TIMEZONE_OFFSET
    return utime.localtime(t)

# --- TELEGRAM ---
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        r = urequests.post(url, json=payload)
        r.close()
    except:
        pass

# --- OTA UPDATE ---
def perform_ota_update(update_link):
    global stop_all_tasks
    stop_all_tasks = True
    utime.sleep(2)  # Allow tasks to stop

    try:
        print("OTA: Downloading new firmware...")
        r = urequests.get(update_link)
        new_code = r.text
        r.close()
        if len(new_code) < 100:
            send_telegram("OTA failed: downloaded code too short.")
            stop_all_tasks = False
            return

        # Save to temp file
        with open("main_new.py", "w") as f:
            f.write(new_code)

        # Rename existing main.py to backup
        if "main.py" in os.listdir():
            os.rename("main.py", "main_backup.py")

        # Move new file to main.py
        os.rename("main_new.py", "main.py")
        send_telegram("OTA update success. Rebooting...")
        utime.sleep(2)
        machine.reset()

    except Exception as e:
        send_telegram(f"OTA failed: {e}")
        stop_all_tasks = False

# --- TELEGRAM COMMAND HANDLER ---
def handle_command(cmd):
    global monitoring_enabled, sensor_mode

    if cmd == "/check":
        send_telegram(f"Digital Reading: {digital_pin.value()}")

    elif cmd == "/telemetry":
        t = get_time()
        time_str = "{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[2], t[1], t[0])
        temp = 25.0  # Placeholder
        send_telegram(f"Telemetry Data = {time_str} - (Digital: {digital_pin.value()}) - CPU temp: {temp:.2f}°C")

    elif cmd == "/time":
        t = get_time()
        time_str = "{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[2], t[1], t[0])
        send_telegram("Time: " + time_str)

    elif cmd == "/stop":
        monitoring_enabled = False
        send_telegram("Monitoring paused")

    elif cmd == "/start":
        monitoring_enabled = True
        send_telegram("Monitoring resumed")

    elif cmd == "/real":
        sensor_mode = "real"
        send_telegram("Mode set to /real")

    elif cmd == "/test":
        sensor_mode = "test"
        send_telegram("Mode set to /test")

    elif cmd == "/all":
        commands = "/check /telemetry /time /stop /start /real /test"
        instructions = "\nOTA Update: Send #update=(link)"
        send_telegram("Commands: " + commands + instructions)

    elif cmd.startswith("#update="):
        link = cmd.replace("#update=", "").strip()
        send_telegram("OTA: Updating from link...")
        perform_ota_update(link)

# --- TELEGRAM LISTENER ---
def listen_telegram():
    last_update_id = None
    while not stop_all_tasks:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=5"
            if last_update_id:
                url += f"&offset={last_update_id + 1}"
            r = urequests.get(url)
            updates = r.json().get("result", [])
            r.close()

            for update in updates:
                msg = update.get("message", {}).get("text", "")
                if msg:
                    handle_command(msg)
                last_update_id = update["update_id"]

        except Exception as e:
            print("Telegram error:", e)
        utime.sleep(1)

# --- SENSOR MONITORING ---
def sensor_monitor():
    while not stop_all_tasks:
        if monitoring_enabled:
            val = digital_pin.value()
            if (sensor_mode == "real" and val == 1) or (sensor_mode == "test" and val == 0):
                send_telegram("Sensor fault, check oxygen pump")
                for _ in range(30):
                    if stop_all_tasks:
                        break
                    utime.sleep(1)
        utime.sleep(1)

# --- MAIN ---
def main():
    connect_wifi()
    utime.sleep(2)

    if internet_connected:
        sync_time()
        utime.sleep(2)
        send_telegram(f"Device Rebooted. SEKATA Bioflok Monitoring System.\nVersion: {VERSION}\nCommands: /check /telemetry /time /stop /start /real /test /all")
        utime.sleep(2)
        onboard_led.on()
    else:
        onboard_led.off()

    _thread.start_new_thread(sensor_monitor, ())
    listen_telegram()

main()
