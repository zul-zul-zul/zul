# main.py — SEKATA Bioflok Monitoring System v0.0.12a

import network
import time
import urequests
import ujson
import machine
import os
import ntptime
from machine import Pin, ADC, WDT

# ==== CONFIG ====
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8
DIGITAL_PIN = Pin(15, Pin.IN)
LED = Pin("LED", Pin.OUT)
VERSION = "v0.0.12a"
UPDATE_FLAG_FILE = "update_id.txt"

monitoring = True
mode = "real"
last_update_id = None
cooldown_active = False

# ==== CONNECT TO WIFI ====
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        print(f"Trying to connect to {ssid}...")
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected to WiFi")
                LED.value(1)
                return True
            time.sleep(1)
        print(f"Failed to connect to {ssid}")
    LED.value(0)
    return False

# ==== NTP SYNC ====
def sync_time():
    for _ in range(5):
        try:
            ntptime.settime()
            print("NTP time synced")
            return True
        except:
            print("NTP sync failed, retrying...")
            time.sleep(2)
    return False

def local_time():
    t = time.localtime(time.time() + TIMEZONE_OFFSET)
    return "{:02d}:{:02d} {} {:02d}/{:02d}/{:04d}".format(
        (t[3] % 12 or 12), t[4], "am" if t[3] < 12 else "pm", t[2], t[1], t[0]
    )

# ==== TELEGRAM FUNCTIONS ====
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = urequests.post(url, json={"chat_id": CHAT_ID, "text": msg})
        response.close()
    except Exception as e:
        print("Telegram send error:", e)

def get_updates():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=5"
        if last_update_id is not None:
            url += f"&offset={last_update_id + 1}"
        response = urequests.get(url)
        updates = response.json()
        response.close()
        return updates.get("result", [])
    except:
        return []

def load_update_id():
    global last_update_id
    try:
        with open(UPDATE_FLAG_FILE) as f:
            last_update_id = int(f.read().strip())
    except:
        last_update_id = None

def save_update_id(update_id):
    try:
        with open(UPDATE_FLAG_FILE, "w") as f:
            f.write(str(update_id))
    except:
        pass

# ==== OTA UPDATE ====
def do_ota_update(link):
    try:
        response = urequests.get(link)
        if response.status_code == 200:
            code = response.text
            with open("main_new.py", "w") as f:
                f.write(code)
                f.flush()
                os.sync()
            if os.stat("main_new.py")[6] > 0:
                if "main.py" in os.listdir():
                    os.rename("main.py", "main_backup.py")
                os.rename("main_new.py", "main.py")
                print("OTA update successful.")
                send_telegram("OTA update installed. Rebooting...")
                safe_reboot()
            else:
                send_telegram("OTA: Downloaded file is empty.")
        else:
            send_telegram("OTA: Failed to download update.")
    except Exception as e:
        print("OTA error:", e)
        send_telegram(f"OTA Error: {e}")

def safe_reboot():
    time.sleep(2)
    print("Rebooting via watchdog...")
    wdt = WDT(timeout=1000)
    time.sleep(2)

# ==== HANDLE COMMANDS ====
def handle_command(cmd):
    global monitoring, mode
    if cmd == "/telemetry":
        msg = f"Telemetry Data = {local_time()} - (Digital: {DIGITAL_PIN.value()}) - CPU temp: N/A"
        send_telegram(msg)
    elif cmd == "/check":
        send_telegram(f"Digital Reading: {DIGITAL_PIN.value()}")
    elif cmd == "/time":
        send_telegram(f"Current Time: {local_time()}")
    elif cmd.startswith("#"):
        if len(cmd) == 13 and cmd[1:].isdigit():
            try:
                h, m, d, M, y = int(cmd[1:3]), int(cmd[3:5]), int(cmd[5:7]), int(cmd[7:9]), int(cmd[9:])
                t = time.mktime((y, M, d, h, m, 0, 0, 0)) - TIMEZONE_OFFSET
                machine.RTC().datetime(time.localtime(t)[:7] + (0,))
                send_telegram("Time manually set.")
            except:
                send_telegram("Invalid time format.")
        elif cmd.startswith("#update="):
            url = cmd[8:]
            do_ota_update(url)
    elif cmd == "/stop":
        monitoring = False
        send_telegram("Monitoring paused.")
    elif cmd == "/start":
        monitoring = True
        send_telegram("Monitoring resumed.")
    elif cmd == "/real":
        mode = "real"
        send_telegram("Mode set to /real")
    elif cmd == "/test":
        mode = "test"
        send_telegram("Mode set to /test")
    elif cmd == "/all":
        cmds = "/telemetry  /check  /time  /stop  /start  /real  /test\nTo update: #update=(link)"
        send_telegram(f"Available Commands:\n{cmds}")

# ==== MAIN LOOP ====
def main():
    global last_update_id
    if not connect_wifi():
        print("No internet.")
        return
    time.sleep(2)

    if not sync_time():
        print("NTP sync failed.")
    time.sleep(2)

    load_update_id()
    send_telegram(f"SEKATA Bioflok Monitoring System Rebooted.\nVersion: {VERSION}\nCommands: /telemetry /check /time /start /stop /real /test /all")
    time.sleep(2)

    while True:
        if monitoring:
            val = DIGITAL_PIN.value()
            if ((mode == "real" and val == 1) or (mode == "test" and val == 0)):
                send_telegram("Sensor fault, check oxygen pump")
                for _ in range(30):
                    LED.toggle()
                    time.sleep(0.5)
                LED.value(1)
        updates = get_updates()
        for update in updates:
            msg = update.get("message", {}).get("text", "")
            if msg:
                handle_command(msg)
            update_id = update["update_id"]
            if update_id:
                last_update_id = update_id
                save_update_id(last_update_id)
        time.sleep(1)

# ==== START ====
main()
