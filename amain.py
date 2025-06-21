# main.py – v0.0.10

import network
import time
import urequests
import machine
import _thread
import ntptime
import gc

# ====== CONFIG ======
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}

BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8
VERSION = "v0.0.10"

# Pins
DIGITAL_PIN = machine.Pin(15, machine.Pin.IN)
led = machine.Pin("LED", machine.Pin.OUT)

# Globals
monitoring = True
mode = "real"
last_update_id = 0
updating = False

# ===== UTILITY FUNCTIONS =====

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        print(f"Connecting to {ssid}...")
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                print("Wi-Fi connected.")
                return True
            time.sleep(1)
    print("Wi-Fi failed.")
    return False

def sync_time():
    for _ in range(5):
        try:
            ntptime.settime()
            rtc = machine.RTC()
            t = time.mktime(time.localtime(time.time() + TIMEZONE_OFFSET))
            tm = time.localtime(t)
            rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            print("Time synced.")
            return True
        except:
            print("Retrying NTP sync...")
            time.sleep(5)
    return False

def send_telegram(msg, retries=3):
    for _ in range(retries):
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {"chat_id": CHAT_ID, "text": msg}
            r = urequests.post(url, json=data)
            r.close()
            return True
        except:
            time.sleep(2)
    return False

def read_digital():
    return DIGITAL_PIN.value()

def format_time():
    t = time.localtime(time.time() + TIMEZONE_OFFSET)
    return "{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(t[3], t[4], t[2], t[1], t[0])

def read_temp():
    sensor_temp = machine.ADC(4)
    reading = sensor_temp.read_u16()
    voltage = reading * 3.3 / 65535
    temperature = 27 - (voltage - 0.706) / 0.001721
    return temperature

def telemetry_report():
    t = format_time()
    digital = read_digital()
    temp = read_temp()
    return f"Telemetry Data = {t} - (Digital: {digital}) - CPU temp: {temp:.2f}°C"

def handle_command(command):
    global monitoring, mode, updating

    if command == "/telemetry":
        send_telegram(telemetry_report())
    elif command == "/check":
        send_telegram(f"Digital Reading: {read_digital()}")
    elif command == "/time":
        send_telegram("Current Time (GMT+8): " + format_time())
    elif command == "/stop":
        monitoring = False
        send_telegram("Monitoring stopped.")
    elif command == "/start":
        monitoring = True
        send_telegram("Monitoring started.")
    elif command == "/real":
        mode = "real"
        send_telegram("Mode set to REAL.")
    elif command == "/test":
        mode = "test"
        send_telegram("Mode set to TEST.")
    elif command == "/all":
        send_telegram("/telemetry  /check  /time  /start  /stop  /real  /test  /update  /all")
    elif command == "/update":
        updating = True
        send_telegram("Starting OTA update...")
        time.sleep(2)
        stop_all_tasks()
        ota_update()

def stop_all_tasks():
    global monitoring
    monitoring = False
    time.sleep(1)

def ota_update():
    try:
        url = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py?v=0.0.10"
        r = urequests.get(url)
        with open("main.py", "w") as f:
            f.write(r.text)
        r.close()
        send_telegram("OTA update complete. Rebooting...")
        time.sleep(2)
        machine.reset()
    except Exception as e:
        send_telegram("OTA failed.")
        print("OTA Error:", e)

def listen_telegram():
    global last_update_id
    while True:
        if updating:
            time.sleep(1)
            continue
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}"
            r = urequests.get(url)
            data = r.json()
            r.close()

            for result in data["result"]:
                message = result["message"]
                text = message.get("text", "")
                last_update_id = result["update_id"]

                if text.startswith("/"):
                    handle_command(text)
                elif text.startswith("#"):
                    try:
                        t = parse_manual_time(text[1:])
                        machine.RTC().datetime(t)
                        send_telegram("Time updated manually.")
                    except:
                        send_telegram("Invalid time format.")
            gc.collect()
        except:
            time.sleep(1)

def parse_manual_time(timestr):
    if len(timestr) != 12:
        raise ValueError
    hh = int(timestr[0:2])
    mm = int(timestr[2:4])
    dd = int(timestr[4:6])
    mo = int(timestr[6:8])
    yyyy = int(timestr[8:12])
    return (yyyy, mo, dd, 0, hh, mm, 0, 0)

def monitor_loop():
    global monitoring
    while True:
        if not monitoring or updating:
            time.sleep(1)
            continue

        value = read_digital()
        fault = (mode == "real" and value == 1) or (mode == "test" and value == 0)

        if fault:
            send_telegram("Sensor fault, check oxygen pump")
            for _ in range(30):
                led.toggle()
                time.sleep(0.5)
            led.on()
        else:
            time.sleep(1)

# ===== MAIN =====

def main():
    global updating
    print("Booting SEKATA Bioflok Monitoring System...")

    # 1. Connect Wi-Fi
    wifi_ok = connect_wifi()
    if wifi_ok:
        led.on()
        time.sleep(2)
    else:
        led.off()
        return

    # 2. Sync time
    time_ok = sync_time()
    if time_ok:
        time.sleep(2)
    else:
        send_telegram("⚠️ NTP time sync failed")
        return

    # 3. Send boot message
    boot_msg = (
        f"SEKATA Bioflok Monitoring System\n"
        f"Device Rebooted. Version: {VERSION}\n"
        "/telemetry  /check  /time  /start  /stop  /real  /test  /update  /all"
    )
    if send_telegram(boot_msg):
        time.sleep(2)

    # 4. Start monitoring and Telegram loop
    _thread.start_new_thread(monitor_loop, ())
    listen_telegram()

main()
