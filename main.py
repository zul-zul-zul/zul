# main.py v1.0.14

import network
import urequests
import utime
import ujson
import machine
import _thread
import gc
from machine import Pin, Timer, reset

# ====== CONFIGURATION ======
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
NTP_SERVER = "pool.ntp.org"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8
VERSION = "v1.0.14"
GITHUB_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py?v=1.0.2"

# ====== STATE VARIABLES ======
monitoring = True
mode = "real"
ota_updating = False
update_id = None

# ====== HARDWARE SETUP ======
led = Pin("LED", Pin.OUT)
digital_pin = Pin(15, Pin.IN)

# ====== WIFI CONNECTION ======
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        print(f"Connecting to {ssid}...")
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected.")
                return True
            utime.sleep(1)
    print("WiFi connection failed.")
    return False

# ====== NTP TIME SYNC ======
def sync_time():
    import socket
    NTP_DELTA = 2208988800
    for _ in range(5):
        try:
            addr = socket.getaddrinfo(NTP_SERVER, 123)[0][-1]
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(5)
            msg = bytearray(48)
            msg[0] = 0x1B
            s.sendto(msg, addr)
            msg = s.recv(48)
            s.close()
            val = int.from_bytes(msg[40:44], 'big') - NTP_DELTA + TIMEZONE_OFFSET
            tm = utime.localtime(val)
            machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            print("Time synchronized.")
            return
        except:
            print("Retrying NTP sync...")
            utime.sleep(10)

# ====== TELEGRAM FUNCTIONS ======
def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        r = urequests.post(url, json=payload)
        r.close()
    except:
        print("Failed to send Telegram message.")

def get_updates():
    global update_id
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        if update_id:
            url += f"?offset={update_id + 1}"
        r = urequests.get(url)
        data = r.json()
        r.close()
        return data.get("result", [])
    except:
        print("Failed to get updates.")
        return []

# ====== TELEGRAM COMMAND HANDLER ======
def handle_command(text):
    global monitoring, mode, ota_updating
    if text == "/check":
        send_message(f"Digital reading: {digital_pin.value()}")
    elif text == "/telemetry":
        now = utime.localtime()
        timestamp = f"{now[3]:02}:{now[4]:02} {now[2]:02}/{now[1]:02}/{now[0]}"
        temp = machine.ADC(4).read_u16() * 3.3 / 65535
        cpu_temp = 27 - (temp - 0.706) / 0.001721
        send_message(f"Telemetry Data = {timestamp} - (Digital: {digital_pin.value()}) - CPU temp: {cpu_temp:.2f}°C")
    elif text == "/time":
        now = utime.localtime()
        send_message("Time now: %02d:%02d %02d/%02d/%d" % (now[3], now[4], now[2], now[1], now[0]))
    elif text.startswith("#") and len(text) == 13:
        try:
            hh = int(text[1:3])
            mm = int(text[3:5])
            dd = int(text[5:7])
            mo = int(text[7:9])
            yy = int(text[9:13])
            machine.RTC().datetime((yy, mo, dd, 0, hh, mm, 0, 0))
            send_message("Manual time set.")
        except:
            send_message("Invalid time format.")
    elif text == "/stop":
        monitoring = False
        send_message("Monitoring paused.")
    elif text == "/start":
        monitoring = True
        send_message("Monitoring resumed.")
    elif text == "/real":
        mode = "real"
        send_message("Set to REAL mode.")
    elif text == "/test":
        mode = "test"
        send_message("Set to TEST mode.")
    elif text == "/all":
        send_message("/telemetry     /check     /time     /stop     /start     /real     /test     /all     /update")
    elif text == "/update":
        ota_updating = True
        utime.sleep(2)
        do_ota_update()

# ====== OTA UPDATE ======
def do_ota_update():
    global ota_updating
    try:
        send_message("OTA: Updating...")
        r = urequests.get(GITHUB_URL)
        with open("main.py", "w") as f:
            f.write(r.text)
        r.close()
        send_message("OTA: Update complete. Rebooting...")
        utime.sleep(2)
        reset()
    except:
        send_message("OTA: Failed to download update.")
        ota_updating = False

# ====== CORE 0: TELEGRAM LOOP ======
def telegram_loop():
    global update_id
    while True:
        if ota_updating:
            break
        updates = get_updates()
        for u in updates:
            update_id = u["update_id"]
            msg = u.get("message", {})
            text = msg.get("text", "")
            handle_command(text)
            gc.collect()
        utime.sleep(2)

# ====== CORE 1: SENSOR MONITORING ======
def core1_monitor():
    while True:
        if ota_updating:
            break
        if monitoring:
            val = digital_pin.value()
            fault = (val == 1 and mode == "real") or (val == 0 and mode == "test")
            if fault:
                send_message("Sensor fault, check oxygen pump")
                for _ in range(30):
                    if ota_updating:
                        return
                    led.toggle()
                    utime.sleep(1)
                continue
        led.value(network.WLAN(network.STA_IF).isconnected())
        utime.sleep(1)

# ====== MAIN ======
if connect_wifi():
    sync_time()
    now = utime.localtime()
    timestamp = "%02d:%02d %02d/%02d/%d" % (now[3], now[4], now[2], now[1], now[0])
    send_message(f"SEKATA Bioflok Monitoring System Booted ({VERSION})\nDevice Reboot and connected to Internet.\n/telemetry     /check     /time     /stop     /start     /real     /test     /all     /update")

_thread.start_new_thread(core1_monitor, ())
telegram_loop()
