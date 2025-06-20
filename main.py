# main.py - v1.0.13 - Stable
import network, urequests, utime, ujson, gc, os
from machine import Pin, ADC, Timer, reset
import _thread
import ntptime

# --- CONFIGURATION ---
VERSION = "v1.0.13 - Stable"
WIFI_SSID = "Makers Studio"
WIFI_PASSWORD = "Jba10600"
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
GITHUB_URL = "https://raw.githubusercontent.com/username/repo/main/main.py?v=1.0.2"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8
DIGITAL_PIN = Pin(15, Pin.IN)
LED = Pin("LED", Pin.OUT)

# --- GLOBAL STATES ---
monitoring = True
mode = "real"
last_alert_time = 0
cooldown_seconds = 30
update_id_file = "last_update.txt"

# --- WIFI CONNECTION ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for attempt in range(5):
        print(f"Connecting to Wi-Fi... Attempt {attempt+1}/5")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected.")
                return True
            utime.sleep(1)
    print("Failed to connect.")
    return False

# --- TIME SYNC ---
def sync_time():
    for attempt in range(5):
        try:
            ntptime.settime()
            print("Time synchronized with NTP.")
            return True
        except:
            print(f"NTP sync failed. Attempt {attempt+1}/5")
            utime.sleep(10)
    return False

def local_time():
    t = utime.time() + TIMEZONE_OFFSET
    return utime.localtime(t)

# --- TELEGRAM ---
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = ujson.dumps({"chat_id": CHAT_ID, "text": msg})
        headers = {"Content-Type": "application/json"}
        r = urequests.post(url, data=payload, headers=headers)
        r.close()
    except Exception as e:
        print("Telegram send error:", e)

def read_update_id():
    try:
        with open(update_id_file) as f:
            return int(f.read())
    except:
        return 0

def save_update_id(uid):
    with open(update_id_file, "w") as f:
        f.write(str(uid))

def acknowledge_all_pending_updates():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        r = urequests.get(url)
        data = r.json()
        r.close()
        updates = data.get("result", [])
        if updates:
            max_update_id = max(u["update_id"] for u in updates)
            save_update_id(max_update_id)
            print(f"Acknowledged up to update_id {max_update_id}")
    except Exception as e:
        print("Acknowledge failed:", e)

def handle_command(text):
    global monitoring, mode

    if text == "/check":
        send_telegram(f"Digital Reading: {DIGITAL_PIN.value()}")
    elif text == "/telemetry":
        t = local_time()
        ts = "{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[2], t[1], t[0])
        temp = read_cpu_temperature()
        send_telegram(f"Telemetry Data = {ts} - (Digital: {DIGITAL_PIN.value()}) - CPU temp: {temp:.2f}°C")
    elif text == "/time":
        t = local_time()
        send_telegram("Time now: {:02d}:{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[5], t[2], t[1], t[0]))
    elif text.startswith("#") and len(text) == 13:
        try:
            hh = int(text[1:3])
            mm = int(text[3:5])
            dd = int(text[5:7])
            MM = int(text[7:9])
            yyyy = int(text[9:])
            t = utime.mktime((yyyy, MM, dd, hh, mm, 0, 0, 0))
            import machine
            machine.RTC().datetime((yyyy, MM, dd, 0, hh, mm, 0, 0))
            send_telegram("Time manually set.")
        except:
            send_telegram("Invalid format. Use #HHMMDDMMYYYY")
    elif text == "/stop":
        monitoring = False
        send_telegram("Monitoring stopped.")
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
        send_telegram("/telemetry     /check     /time     /stop     /start     /real     /test     /all     /update")
    elif text == "/update":
        do_ota_update()

def telegram_loop():
    last_update = read_update_id()
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update + 1}"
            r = urequests.get(url)
            data = r.json()
            r.close()

            for result in data["result"]:
                last_update = result["update_id"]
                save_update_id(last_update)

                message = result.get("message", {})
                text = message.get("text")
                if text:
                    handle_command(text)
            gc.collect()
        except Exception as e:
            print("Telegram error:", e)
        utime.sleep(1)

# --- TEMPERATURE ---
def read_cpu_temperature():
    sensor = ADC(4)
    reading = sensor.read_u16() * 3.3 / 65535
    return 27 - (reading - 0.706)/0.001721

# --- OTA UPDATE ---
def do_ota_update():
    try:
        send_telegram("OTA: Downloading update...")
        r = urequests.get(GITHUB_URL)
        new_code = r.text
        r.close()
        with open("main.py", "w") as f:
            f.write(new_code)
        send_telegram("OTA: Update complete. Rebooting...")
        utime.sleep(2)
        reset()
    except Exception as e:
        send_telegram("OTA: Failed to update.")
        print("OTA error:", e)

# --- MONITORING THREAD ---
def core1_monitor():
    global last_alert_time

    while True:
        LED.value(network.WLAN(network.STA_IF).isconnected())
        if not monitoring:
            utime.sleep(1)
            continue

        value = DIGITAL_PIN.value()
        alert = False

        if mode == "real" and value == 1:
            alert = True
        elif mode == "test" and value == 0:
            alert = True

        if alert and (utime.time() - last_alert_time > cooldown_seconds):
            send_telegram("Sensor fault, check oxygen pump")
            last_alert_time = utime.time()

            for _ in range(cooldown_seconds):
                LED.toggle()
                utime.sleep(1)
            LED.value(1 if network.WLAN(network.STA_IF).isconnected() else 0)
        else:
            utime.sleep(1)

# --- MAIN EXECUTION ---
if connect_wifi():
    sync_time()
    acknowledge_all_pending_updates()
    boot_msg = f"SEKATA Bioflok Monitoring System ({VERSION})\nDevice Reboot and connected to Internet.\n/telemetry     /check     /time     /stop     /start     /real     /test     /all     /update"
    send_telegram(boot_msg)
else:
    print("No WiFi. Skipping Telegram.")

_thread.start_new_thread(core1_monitor, ())
telegram_loop()
