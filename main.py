import network
import urequests
import utime
import machine
import _thread
import ntptime
import gc
from machine import Pin, ADC

# ========== Configuration ==========
VERSION = "beta v0.0.3"
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
GITHUB_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py?v=0.0.3"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8

# ========== Flags ==========
monitoring = True
mode = "real"
ota_updating = False
core1_has_exited = False
core1_running = False
last_update_id = None

# ========== Pins ==========
digital_sensor = Pin(15, Pin.IN)
led = Pin("LED", Pin.OUT)

# ========== WiFi ==========
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, pwd in WIFI_CREDENTIALS.items():
        wlan.connect(ssid, pwd)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected to", ssid)
                return True
            utime.sleep(1)
    return False

# ========== NTP ==========
def sync_time():
    for _ in range(5):
        try:
            ntptime.settime()
            now = utime.time() + TIMEZONE_OFFSET
            tm = utime.localtime(now)
            machine.RTC().datetime((tm[0], tm[1], tm[2], 0, tm[3], tm[4], tm[5], 0))
            return True
        except:
            utime.sleep(10)
    return False

def format_time():
    t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
    hour = t[3]
    ampm = "am" if hour < 12 else "pm"
    hour = hour if 1 <= hour <= 12 else abs(hour - 12)
    return "{}:{:02d} {} {}/{}/{}".format(hour, t[4], ampm, t[2], t[1], t[0])

# ========== Telegram ==========
def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        r = urequests.post(url, json=payload)
        r.close()
    except:
        pass

def get_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
    if last_update_id:
        url += f"&offset={last_update_id + 1}"
    try:
        r = urequests.get(url)
        data = r.json()
        r.close()
        return data["result"]
    except:
        return []

# ========== OTA ==========
def do_ota_update():
    global ota_updating
    send_message("OTA: Starting update...")
    try:
        # Wait for core 1 to exit
        for _ in range(10):
            if core1_has_exited:
                break
            utime.sleep(1)

        r = urequests.get(GITHUB_URL)
        with open("main.py", "w") as f:
            f.write(r.text)
        r.close()
        send_message("OTA: Update complete. Rebooting...")
        utime.sleep(2)
        machine.reset()
    except Exception as e:
        send_message("OTA: Failed - " + str(e))
        ota_updating = False

# ========== Core 1 ==========
def core1_monitor():
    global core1_has_exited, core1_running
    core1_running = True
    blink_time = 0.5
    while not ota_updating:
        wlan = network.WLAN(network.STA_IF)
        led.value(wlan.isconnected())

        if monitoring:
            val = digital_sensor.value()
            trigger = (val == 1 if mode == "real" else val == 0)
            if trigger:
                send_message("Sensor fault, check oxygen pump")
                for _ in range(30):
                    led.toggle()
                    utime.sleep(0.5)
            utime.sleep(1)
        else:
            utime.sleep(1)

    core1_has_exited = True
    core1_running = False

# ========== Core 0 ==========
def handle_command(cmd):
    global monitoring, mode, ota_updating, core1_running
    if cmd == "/check":
        send_message(f"Digital reading: {digital_sensor.value()}")
    elif cmd == "/telemetry":
        msg = f"Telemetry = {format_time()} - (Digital: {digital_sensor.value()}) - CPU temp: 33.13°C"
        send_message(msg)
    elif cmd == "/time":
        send_message("Current time: " + format_time())
    elif cmd == "/stop":
        monitoring = False
        send_message("Monitoring paused.")
    elif cmd == "/start":
        monitoring = True
        send_message("Monitoring resumed.")
    elif cmd == "/real":
        mode = "real"
        send_message("Mode set to /real.")
    elif cmd == "/test":
        mode = "test"
        send_message("Mode set to /test.")
    elif cmd == "/all":
        send_message("/telemetry  /check  /time  /stop  /start  /real  /test  /all  /update")
    elif cmd == "/update":
        if not ota_updating and core1_running:
            ota_updating = True
            send_message("Preparing for OTA update...")
            # Wait before OTA thread to ensure core1 exits
            utime.sleep(1)
            _thread.start_new_thread(do_ota_update, ())

def listen_telegram():
    global last_update_id
    while True:
        if ota_updating:
            utime.sleep(1)
            continue
        results = get_updates()
        for msg in results:
            if "message" in msg and "text" in msg["message"]:
                text = msg["message"]["text"]
                last_update_id = msg["update_id"]
                handle_command(text)
        utime.sleep(2)
        gc.collect()

# ========== Main ==========
def main():
    if not connect_wifi():
        print("No Wi-Fi.")
        return

    sync_time()

    boot_msg = f"SEKATA Bioflok Monitoring System\nDevice Reboot and connected to Internet. Version: {VERSION}\nCommands: /telemetry  /check  /time  /stop  /start  /real  /test  /all  /update"
    send_message(boot_msg)

    # Start core1 if not running
    if not core1_running:
        _thread.start_new_thread(core1_monitor, ())

    listen_telegram()

main()
