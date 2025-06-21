# main.py - SEKATA Bioflok Monitoring System v0.0.11b 

import network
import urequests
import time
import machine
import _thread
import ntptime
import gc
import os
from machine import Pin

# === Configuration ===
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
GITHUB_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py?v=0.0.11b"
VERSION = "beta v0.0.11b"

# === Global Variables ===
led = Pin("LED", Pin.OUT)
digital_pin = Pin(15, Pin.IN)
monitoring = True
mode = "real"  # can be 'real' or 'test'
connected = False
stop_flag = False
update_lock = _thread.allocate_lock()

# === WiFi Connection ===
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        print(f"Connecting to {ssid}...")
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                global connected
                connected = True
                print("WiFi connected")
                led.on()
                return True
            time.sleep(1)
    print("Failed to connect to WiFi")
    led.off()
    return False

# === Time Sync ===
def sync_time():
    for _ in range(5):
        try:
            ntptime.settime()
            time.timezone(8 * 3600)  # GMT+8
            print("Time synchronized")
            return True
        except:
            print("Retrying NTP sync...")
            time.sleep(10)
    return False

# === Telegram ===
def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        r = urequests.post(url, json=payload)
        r.close()
    except Exception as e:
        print("Telegram error:", e)

# === Update ID Handling ===
def load_last_update_id():
    try:
        with open("update_id.txt", "r") as f:
            return int(f.read().strip())
    except:
        return None

def save_last_update_id(update_id):
    try:
        with open("update_id.txt", "w") as f:
            f.write(str(update_id))
    except:
        pass

# === Handle Commands ===
def handle_command(text):
    global monitoring, mode, stop_flag
    if text == "/check":
        send_telegram_message(f"Digital reading: {digital_pin.value()}")
    elif text == "/telemetry":
        t = time.localtime()
        timestamp = "{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[2], t[1], t[0])
        temp = get_cpu_temperature()
        send_telegram_message(f"Telemetry Data = {timestamp} - (Digital: {digital_pin.value()}) - CPU temp: {temp:.2f}°C")
    elif text == "/time":
        t = time.localtime()
        send_telegram_message("Time: {:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[2], t[1], t[0]))
    elif text.startswith("#"):
        try:
            hh = int(text[1:3])
            mm = int(text[3:5])
            dd = int(text[5:7])
            mo = int(text[7:9])
            yy = int(text[9:13])
            tm = time.mktime((yy, mo, dd, hh, mm, 0, 0, 0)) - time.timezone
            machine.RTC().datetime(time.localtime(tm)[:7] + (0,))
            send_telegram_message("Time manually set")
        except:
            send_telegram_message("Invalid time format")
    elif text == "/stop":
        monitoring = False
        send_telegram_message("Monitoring paused")
    elif text == "/start":
        monitoring = True
        send_telegram_message("Monitoring resumed")
    elif text == "/real":
        mode = "real"
        send_telegram_message("Mode set to REAL")
    elif text == "/test":
        mode = "test"
        send_telegram_message("Mode set to TEST")
    elif text == "/all":
        send_telegram_message("/telemetry  /check  /time  /start  /stop  /real  /test  /all  /update")
    elif text == "/update":
        stop_flag = True
        time.sleep(2)
        perform_ota_update()

# === Listen Telegram ===
def listen_telegram():
    last_update = load_last_update_id()
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=5"
            if last_update:
                url += f"&offset={last_update + 1}"
            r = urequests.get(url)
            data = r.json()
            r.close()
            for update in data["result"]:
                msg = update.get("message", {}).get("text", "")
                if msg:
                    handle_command(msg)
                last_update = update["update_id"]
                save_last_update_id(last_update)
        except Exception as e:
            print("Error polling Telegram:", e)
        time.sleep(1)
        if stop_flag:
            break

# === Temperature ===
def get_cpu_temperature():
    sensor_temp = machine.ADC(4)
    reading = sensor_temp.read_u16() * (3.3 / 65535)
    temp = 27 - (reading - 0.706) / 0.001721
    return temp

# === OTA Update ===
def perform_ota_update():
    try:
        r = urequests.get(GITHUB_URL)
        with open("main.py", "w") as f:
            f.write(r.text)
        r.close()
        send_telegram_message("OTA: Update successful. Rebooting...")
        time.sleep(2)
        machine.reset()
    except Exception as e:
        send_telegram_message(f"OTA: Failed - {e}")

# === LED Internet Indicator (Core 1) ===
def core1_task():
    while True:
        led.value(connected)
        time.sleep(1)

# === Main Logic ===
def main():
    connect_wifi()
    time.sleep(2)
    sync_time()
    time.sleep(2)
    send_telegram_message(f"Device Rebooted. SEKATA Bioflok Monitoring System. Version: {VERSION}\nCommands: /telemetry  /check  /time  /start  /stop  /real  /test  /all  /update")
    time.sleep(2)
    _thread.start_new_thread(core1_task, ())
    listen_telegram()

# === Start ===
main()
