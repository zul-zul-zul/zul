# SEKATA Bioflok Monitoring System - OTA Safe Version
# Version: beta v0.0.11a

import network
import time
import urequests as requests
import ujson as json
import machine
import os
import _thread
import gc

# ====== CONFIG ======
WIFI_SSID = "Makers Studio"
WIFI_PASSWORD = "Jba10600"
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
GITHUB_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py?v=0.0.11a"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8

# ====== GLOBAL STATE ======
last_update_id = None
monitoring = True
mode = "real"
digital_pin = machine.Pin(15, machine.Pin.IN)
led = machine.Pin("LED", machine.Pin.OUT)
updating = False

# ====== FUNCTIONS ======
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for i in range(5):
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for j in range(10):
            if wlan.isconnected():
                print("Connected to Wi-Fi")
                return True
            time.sleep(1)
        print("Retry Wi-Fi...", i+1)
    print("Failed to connect to Wi-Fi")
    return False

def sync_time():
    import ntptime
    for _ in range(5):
        try:
            ntptime.settime()
            rtc = machine.RTC()
            epoch = time.mktime(time.localtime()) + TIMEZONE_OFFSET
            tm = time.localtime(epoch)
            rtc.datetime((tm[0], tm[1], tm[2], tm[6]+1, tm[3], tm[4], tm[5], 0))
            print("Time synced")
            return True
        except:
            print("Retry time sync...")
            time.sleep(10)
    return False

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        r = requests.post(url, json=payload)
        r.close()
    except Exception as e:
        print("Telegram send error:", e)

def get_cpu_temp():
    sensor_temp = machine.ADC(4)
    reading = sensor_temp.read_u16()
    voltage = reading * 3.3 / 65535
    return 27 - (voltage - 0.706)/0.001721

def format_time():
    tm = time.localtime()
    hour = tm[3]
    ampm = "am" if hour < 12 else "pm"
    hour = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
    return f"{hour:02d}:{tm[4]:02d} {ampm} {tm[2]:02d}/{tm[1]:02d}/{tm[0]}"

def read_digital():
    return digital_pin.value()

def handle_command(command):
    global monitoring, mode, updating
    if command == "/telemetry":
        msg = f"Telemetry Data = {format_time()} - (Digital: {read_digital()}) - CPU temp: {get_cpu_temp():.2f}\u00b0C"
        send_telegram(msg)
    elif command == "/check":
        send_telegram(f"Digital Reading: {read_digital()}")
    elif command == "/stop":
        monitoring = False
        send_telegram("Monitoring stopped.")
    elif command == "/start":
        monitoring = True
        send_telegram("Monitoring resumed.")
    elif command == "/real":
        mode = "real"
        send_telegram("Mode set to REAL")
    elif command == "/test":
        mode = "test"
        send_telegram("Mode set to TEST")
    elif command == "/all":
        send_telegram("/telemetry     /check     /time     /stop     /start     /real     /test     /all     /update")
    elif command == "/time":
        send_telegram(format_time())
    elif command == "/update":
        updating = True
        send_telegram("Starting OTA update...")
        time.sleep(2)
        ota_update()


def listen_telegram():
    global last_update_id, updating
    while not updating:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=5"
            if last_update_id:
                url += f"&offset={last_update_id}"
            r = requests.get(url)
            updates = r.json()["result"]
            r.close()
            for update in updates:
                last_update_id = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    command = update["message"]["text"]
                    handle_command(command)
            time.sleep(1)
        except Exception as e:
            print("Telegram loop error:", e)
            time.sleep(2)

def monitor_loop():
    global updating
    while not updating:
        if monitoring:
            digital_value = read_digital()
            fault = (digital_value == 1) if mode == "real" else (digital_value == 0)
            if fault:
                send_telegram("Sensor fault, check oxygen pump")
                for _ in range(30):
                    led.toggle()
                    time.sleep(0.5)
            else:
                led.value(True)
        else:
            time.sleep(1)
        time.sleep(1)

def ota_update():
    try:
        r = requests.get(GITHUB_URL)
        code = r.text
        r.close()
        with open("main_tmp.py", "w") as f:
            f.write(code)
        if "main.py" in os.listdir():
            os.remove("main.py")
        os.rename("main_tmp.py", "main.py")
        send_telegram("OTA: Update completed. Rebooting...")
        time.sleep(2)
        machine.reset()
    except Exception as e:
        print("OTA update failed:", e)
        send_telegram("OTA: Failed to update.")
        updating = False

# ====== MAIN ======
def main():
    if connect_wifi():
        led.value(True)
        time.sleep(2)
        sync_time()
        time.sleep(2)
        send_telegram("SEKATA Bioflok Monitoring System.\nDevice Rebooted. Version: beta v0.0.11a\n/telemetry     /check     /time     /stop     /start     /real     /test     /all     /update")
        time.sleep(2)
        _thread.start_new_thread(monitor_loop, ())
        listen_telegram()
    else:
        led.value(False)

main()
