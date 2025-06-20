# main.py - v1.0.2

OTA_VERSION = "1.0.2"

import network
import urequests
import utime
import ujson
import machine
import _thread
import gc
import ntptime
import os
from machine import Pin

WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}

BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
OTA_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/main/main.py"

DIGITAL_PIN = Pin(15, Pin.IN)
LED = Pin("LED", Pin.OUT)
TIMEZONE_OFFSET = 8 * 3600
last_update_id = None

monitoring = True
mode = "real"
wifi_connected = False

def connect_wifi(max_retries=5, wait_time=10):
    global wifi_connected
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        for attempt in range(max_retries):
            if not wlan.isconnected():
                wlan.connect(ssid, password)
                for _ in range(wait_time):
                    if wlan.isconnected():
                        break
                    utime.sleep(1)
            if wlan.isconnected():
                wifi_connected = True
                return True
    wifi_connected = False
    return False

def sync_time(max_retries=5, wait_time=10):
    for attempt in range(max_retries):
        try:
            ntptime.settime()
            return True
        except:
            utime.sleep(wait_time)
    return False

def get_local_time():
    t = utime.time() + TIMEZONE_OFFSET
    tm = utime.localtime(t)
    return "{:02}:{:02} {:02}/{:02}/{:04}".format(tm[3], tm[4], tm[2], tm[1], tm[0])

def get_hour_min():
    t = utime.time() + TIMEZONE_OFFSET
    tm = utime.localtime(t)
    return tm[3], tm[4]

def send_telegram(text):
    try:
        urequests.post(TELEGRAM_URL + "/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text
        }).close()
    except:
        pass

def get_updates():
    global last_update_id
    url = TELEGRAM_URL + "/getUpdates?timeout=10"
    if last_update_id:
        url += f"&offset={last_update_id + 1}"
    try:
        r = urequests.get(url)
        res = r.json()
        r.close()
        return res.get("result", [])
    except:
        return []

def perform_ota_update():
    try:
        r = urequests.get(OTA_URL)
        new_code = r.text
        r.close()

        with open("main.py", "w") as f:
            f.write(new_code)

        send_telegram("✅ OTA update complete. Rebooting now...")
        utime.sleep(2)
        machine.reset()

    except Exception as e:
        send_telegram("❌ OTA update failed.")

def handle_command(msg):
    global last_update_id, monitoring, mode
    last_update_id = msg["update_id"]
    chat_id = str(msg["message"]["chat"]["id"])
    text = msg["message"].get("text", "").strip()

    if chat_id != CHAT_ID:
        return

    if text == "/check":
        send_telegram(f"Digital Reading (GP15): {DIGITAL_PIN.value()}")
    elif text == "/telemetry":
        temp = machine.cpu().temperature()
        timestamp = get_local_time()
        send_telegram(f"Telemetry Data = {timestamp} - (Digital: {DIGITAL_PIN.value()}) - CPU temp: {temp:.2f}°C")
    elif text == "/time":
        send_telegram(f"Current Time: {get_local_time()}")
    elif text.startswith("#") and len(text) == 13:
        try:
            hh = int(text[1:3])
            mm = int(text[3:5])
            dd = int(text[5:7])
            MM = int(text[7:9])
            yyyy = int(text[9:])
            t = utime.mktime((yyyy, MM, dd, hh, mm, 0, 0, 0))
            machine.RTC().datetime(utime.localtime(t - TIMEZONE_OFFSET)[:7] + (0,))
            send_telegram("Time updated manually.")
        except:
            send_telegram("Invalid time format.")
    elif text == "/stop":
        monitoring = False
        send_telegram("Monitoring paused.")
    elif text == "/start":
        monitoring = True
        send_telegram("Monitoring resumed.")
    elif text == "/real":
        mode = "real"
        send_telegram("Mode set to /real.")
    elif text == "/test":
        mode = "test"
        send_telegram("Mode set to /test.")
    elif text == "/all":
        send_telegram("/telemetry     /check     /time     /start     /stop     /real     /test     /all     /update")
    elif text == "/update":
        send_telegram("Starting OTA update...")
        perform_ota_update()

def core1_task():
    global wifi_connected
    last_hour = -1
    cooldown = False

    def blink_led():
        for _ in range(30):
            LED.toggle()
            utime.sleep(0.5)

    while True:
        if network.WLAN(network.STA_IF).isconnected():
            wifi_connected = True
            if not cooldown:
                LED.value(1)
        else:
            wifi_connected = False
            LED.value(0)

        if monitoring:
            value = DIGITAL_PIN.value()
            alert = False

            if mode == "real" and value == 1:
                alert = True
            elif mode == "test" and value == 0:
                alert = True

            if alert:
                send_telegram("Sensor fault, check oxygen pump")
                cooldown = True
                blink_led()
                cooldown = False
            else:
                utime.sleep(1)

        h, m = get_hour_min()
        if m == 0 and h != last_hour:
            temp = machine.cpu().temperature()
            timestamp = get_local_time()
            send_telegram(f"Telemetry Data = {timestamp} - (Digital: {DIGITAL_PIN.value()}) - CPU temp: {temp:.2f}°C")
            last_hour = h

        utime.sleep(0.5)

def main():
    if not connect_wifi():
        return
    sync_time()

    send_telegram(f"📡 SEKATA Bioflok Monitoring System v{OTA_VERSION}")
    utime.sleep(2)
    send_telegram("Device Reboot and connected to Internet.")
    utime.sleep(2)
    send_telegram("Available commands:\n/telemetry     /check     /time     /start     /stop     /real     /test     /all     /update")

    _thread.start_new_thread(core1_task, ())

    while True:
        updates = get_updates()
        for msg in updates:
            handle_command(msg)
            gc.collect()
        utime.sleep(2)

main()
