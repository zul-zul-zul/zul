# SEKATA Bioflok Monitoring System - v0.0.12c

import network
import urequests
import time
import machine
import _thread
import ujson
import os
from ntptime import settime
from machine import Pin, WDT

# === Configuration ===
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8
VERSION = "v0.0.12c"
LED = Pin("LED", Pin.OUT)
SENSOR = Pin(15, Pin.IN)

# === Global Flags ===
monitoring = True
mode = "real"
connected = False

# === LED Blink Task on Core 1 ===
def led_blink_no_wifi():
    while True:
        if not connected:
            LED.toggle()
            time.sleep(0.2)
        else:
            LED.value(1)
            time.sleep(1)

# === Connect to WiFi ===
def connect_wifi():
    global connected
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, pwd in WIFI_CREDENTIALS.items():
        wlan.connect(ssid, pwd)
        for _ in range(20):
            if wlan.isconnected():
                connected = True
                print(f"[WiFi] Connected to {ssid}")
                return
            time.sleep(0.5)
    connected = False
    print("[WiFi] Failed to connect.")

# === Time Handling ===
def sync_time():
    try:
        settime()
        print("[Time] Synced with NTP")
    except:
        print("[Time] Failed to sync NTP")

def get_local_time():
    t = time.localtime(time.time() + TIMEZONE_OFFSET)
    return "{:02}:{:02}:{:02} {:02}/{:02}/{}".format(t[3], t[4], t[5], t[2], t[1], t[0])

# === Telegram Messaging ===
def send_msg(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = ujson.dumps({"chat_id": CHAT_ID, "text": text})
        headers = {"Content-Type": "application/json"}
        r = urequests.post(url, data=payload, headers=headers)
        r.close()
    except Exception as e:
        print(f"[Telegram] Error sending message: {e}")

# === OTA Update with Safe Reboot ===
def ota_update(url):
    print("[OTA] Starting update...")
    try:
        r = urequests.get(url)
        code = r.text
        r.close()
        if len(code) < 100:
            send_msg("[OTA] Update failed: file too short.")
            return
        with open("main_new.py", "w") as f:
            f.write(code)
            f.flush()
        os.rename("main.py", "main_backup.py")
        os.rename("main_new.py", "main.py")
        send_msg("[OTA] Update success. Rebooting...")
        time.sleep(2)
        wdt = WDT(timeout=1000)  # Watchdog triggers reset
        time.sleep(2)
    except Exception as e:
        send_msg(f"[OTA] Update error: {e}")

# === Telegram Command Loop ===
def telegram_loop():
    update_id = load_update_id()
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10&offset={update_id}"
            r = urequests.get(url)
            data = r.json()
            r.close()
            for update in data["result"]:
                update_id = update["update_id"] + 1
                save_update_id(update_id)
                msg = update.get("message", {}).get("text", "")
                if msg == "/check":
                    send_msg(f"[Sensor] Value: {SENSOR.value()}")
                elif msg == "/time":
                    send_msg(f"[Time] {get_local_time()}")
                elif msg == "/stop":
                    global monitoring
                    monitoring = False
                    send_msg("[Monitor] Stopped")
                elif msg == "/start":
                    monitoring = True
                    send_msg("[Monitor] Started")
                elif msg == "/real":
                    global mode
                    mode = "real"
                    send_msg("[Mode] Real mode")
                elif msg == "/test":
                    mode = "test"
                    send_msg("[Mode] Test mode")
                elif msg.startswith("#update="):
                    ota_update(msg.split("=", 1)[-1])
                elif msg.startswith("#") and len(msg) == 17:
                    try:
                        hh = int(msg[1:3])
                        mm = int(msg[3:5])
                        dd = int(msg[5:7])
                        MM = int(msg[7:9])
                        yyyy = int(msg[9:13])
                        ss = int(msg[13:15])
                        machine.RTC().datetime((yyyy, MM, dd, 0, hh, mm, ss, 0))
                        send_msg(f"[Time] Set to {hh}:{mm} {dd}/{MM}/{yyyy}")
                    except:
                        send_msg("[Time] Failed to set time")
                elif msg == "/all":
                    send_msg("/check, /time, /start, /stop, /real, /test, /all\\nUse #update=URL for OTA.")
            time.sleep(1)
        except Exception as e:
            print(f"[Telegram] Error: {e}")
            time.sleep(3)

# === Sensor Monitoring ===
def monitor_loop():
    last_state = SENSOR.value()
    while True:
        if monitoring:
            val = SENSOR.value()
            trigger = (val == 1) if mode == "real" else (val == 0)
            if trigger and val != last_state:
                send_msg(f"[ALERT] Sensor Triggered! ({val})\\n{get_local_time()}")
                for _ in range(30):
                    LED.toggle()
                    time.sleep(0.5)
                LED.value(connected)
            last_state = val
        time.sleep(0.2)

# === Persistent update_id ===
def save_update_id(uid):
    try:
        with open("update_id.txt", "w") as f:
            f.write(str(uid))
    except:
        pass

def load_update_id():
    try:
        with open("update_id.txt") as f:
            return int(f.read())
    except:
        return 0

# === Main Entry ===
def main():
    print(f"[BOOT] SEKATA Bioflok v{VERSION}")
    connect_wifi()
    time.sleep(2)
    if connected:
        sync_time()
        time.sleep(2)
        send_msg(f"[BOOT] SEKATA started {get_local_time()} - v{VERSION}")
        time.sleep(2)
        _thread.start_new_thread(telegram_loop, ())
    _thread.start_new_thread(led_blink_no_wifi, ())
    monitor_loop()

main()
