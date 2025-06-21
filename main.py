# main.py - v0.0.12 with Safe OTA Update (Dual-File) 

import network
import urequests
import utime
import machine
import gc
import ujson
import _thread
import os

# ========== CONFIGURATION ==========
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT +8
VERSION = "v0.0.12"
DIGITAL_PIN = machine.Pin(15, machine.Pin.IN)
LED = machine.Pin("LED", machine.Pin.OUT)

monitoring_enabled = True
sensor_mode = "real"  # or "test"
last_update_id = 0

# ========== CONNECT TO WIFI ==========
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                print(f"Connected to {ssid}")
                LED.value(1)
                return True
            utime.sleep(1)
    LED.value(0)
    return False

# ========== NTP TIME SYNC ==========
def sync_time():
    import ntptime
    ntptime.host = "pool.ntp.org"
    for _ in range(5):
        try:
            ntptime.settime()
            rtc = machine.RTC()
            t = utime.time() + TIMEZONE_OFFSET
            tm = utime.localtime(t)
            rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            print("Time synced")
            return True
        except:
            utime.sleep(2)
    return False

# ========== TELEGRAM FUNCTIONS ==========
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_telegram_message(text):
    try:
        url = f"{TELEGRAM_URL}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        response = urequests.post(url, json=payload)
        response.close()
    except:
        pass

# ========== HANDLE TELEGRAM COMMANDS ==========
def handle_command(command):
    global monitoring_enabled, sensor_mode

    if command == "/check":
        send_telegram_message(f"Digital Reading: {DIGITAL_PIN.value()}")

    elif command == "/telemetry":
        t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
        timestamp = f"{t[3]:02}:{t[4]:02} {t[2]:02}/{t[1]:02}/{t[0]}"
        send_telegram_message(f"Telemetry = {timestamp} - (Digital: {DIGITAL_PIN.value()}) - CPU Temp: N/A")

    elif command == "/time":
        t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
        send_telegram_message(f"Time now = {t[3]:02}:{t[4]:02}:{t[5]:02} {t[2]:02}/{t[1]:02}/{t[0]}")

    elif command == "/stop":
        monitoring_enabled = False
        send_telegram_message("Monitoring paused")

    elif command == "/start":
        monitoring_enabled = True
        send_telegram_message("Monitoring resumed")

    elif command == "/real":
        sensor_mode = "real"
        send_telegram_message("Sensor mode set to REAL")

    elif command == "/test":
        sensor_mode = "test"
        send_telegram_message("Sensor mode set to TEST")

    elif command == "/all":
        msg = (
            "/telemetry     /check     /time     /stop\n"
            "/start     /real     /test     /all\n"
            "To update: use #update=(link)"
        )
        send_telegram_message(msg)

    elif command.startswith("#update="):
        link = command.replace("#update=", "")
        ota_update(link)

# ========== OTA UPDATE ==========
def ota_update(link):
    try:
        send_telegram_message("OTA: Starting download...")
        r = urequests.get(link)
        code = r.text
        r.close()

        if len(code) < 1000 or "VERSION" not in code:
            send_telegram_message("OTA: Invalid or empty update file.")
            return

        with open("main_new.py", "w") as f:
            f.write(code)

        # Rename sequence
        if "main_backup.py" in os.listdir():
            os.remove("main_backup.py")
        os.rename("main.py", "main_backup.py")
        os.rename("main_new.py", "main.py")

        send_telegram_message("OTA: Update successful. Rebooting...")
        utime.sleep(2)
        machine.reset()

    except Exception as e:
        send_telegram_message("OTA: Failed to update.")
        print("OTA Error:", e)

# ========== TELEGRAM POLLING ==========
def listen_telegram():
    global last_update_id
    while True:
        try:
            url = f"{TELEGRAM_URL}/getUpdates?timeout=5&offset={last_update_id}"
            r = urequests.get(url)
            data = r.json()
            r.close()

            for update in data["result"]:
                last_update_id = update["update_id"] + 1
                message = update["message"]
                if "text" in message:
                    handle_command(message["text"])

            utime.sleep(1)
        except:
            utime.sleep(2)

# ========== SENSOR MONITORING ==========
def monitor_sensor():
    while True:
        if monitoring_enabled:
            val = DIGITAL_PIN.value()
            fault = False
            if sensor_mode == "real" and val == 1:
                fault = True
            elif sensor_mode == "test" and val == 0:
                fault = True

            if fault:
                send_telegram_message("Sensor fault, check oxygen pump")
                for _ in range(30):
                    utime.sleep(1)

        utime.sleep(1)

# ========== MAIN ==========
def main():
    print(f"Starting SEKATA v{VERSION}")
    if not connect_wifi():
        print("Wi-Fi Failed")
        return
    utime.sleep(2)
    sync_time()
    utime.sleep(2)
    send_telegram_message(f"SEKATA Bioflok Monitoring System v{VERSION}\nDevice Rebooted and connected to Internet.\n/telemetry     /check     /time     /stop\n/start     /real     /test     /all")
    utime.sleep(2)
    _thread.start_new_thread(monitor_sensor, ())
    listen_telegram()

main()
