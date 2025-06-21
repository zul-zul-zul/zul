# main.py — beta v0.0.6

import network, utime, urequests, machine, _thread, gc
from machine import Pin

# =====================[ CONFIG ]=====================

VERSION = "beta v0.0.6"
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT +8
DIGITAL_PIN = 15
LED = Pin("LED", Pin.OUT)
UPDATE_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py?v=0.0.6"
UPDATE_ID_FILE = "update_id.txt"

# =====================[ GLOBALS ]=====================

monitoring = True
mode = "real"
ota_updating = False
core1_should_stop = False
core1_has_exited = False
last_update_id = None
digital = Pin(DIGITAL_PIN, Pin.IN)

# =====================[ WIFI ]=====================

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, pwd in WIFI_CREDENTIALS.items():
        print(f"Trying WiFi: {ssid}")
        wlan.connect(ssid, pwd)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected:", wlan.ifconfig())
                return True
            utime.sleep(1)
    print("Failed to connect to any WiFi")
    return False

# =====================[ TIME ]=====================

def sync_time():
    import ntptime
    for _ in range(5):
        try:
            ntptime.settime()
            rtc = machine.RTC()
            t = utime.time() + TIMEZONE_OFFSET
            tm = utime.localtime(t)
            rtc.datetime((tm[0], tm[1], tm[2], tm[6]+1, tm[3], tm[4], tm[5], 0))
            print("Time synced.")
            return
        except:
            print("NTP sync failed. Retrying...")
            utime.sleep(10)

# =====================[ TELEGRAM ]=====================

def send_message(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        r = urequests.post(url, json=payload)
        r.close()
    except:
        print("Failed to send Telegram message.")

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
        if offset:
            url += f"&offset={offset}"
        r = urequests.get(url)
        data = r.json()
        r.close()
        return data.get("result", [])
    except:
        return []

def load_update_id():
    global last_update_id
    try:
        with open(UPDATE_ID_FILE) as f:
            last_update_id = int(f.read().strip())
    except:
        last_update_id = None

def save_update_id(uid):
    with open(UPDATE_ID_FILE, "w") as f:
        f.write(str(uid))

# =====================[ TELEMETRY ]=====================

def get_telemetry():
    t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
    time_str = "{:02}:{:02}:{:02} {:02}/{:02}/{:04}".format(t[3], t[4], t[5], t[2], t[1], t[0])
    digital_val = digital.value()
    temp = get_cpu_temp()
    return f"Telemetry Data = {time_str} - (Digital: {digital_val}) - CPU temp: {temp:.2f}°C"

def get_cpu_temp():
    try:
        sensor_temp = machine.ADC(4)
        reading = sensor_temp.read_u16() * (3.3 / 65535)
        temp_c = 27 - (reading - 0.706) / 0.001721
        return temp_c
    except:
        return -99

# =====================[ OTA UPDATE ]=====================

def do_ota_update():
    global ota_updating
    ota_updating = True
    send_message("OTA: Starting update. Please wait...")
    utime.sleep(2)

    try:
        r = urequests.get(UPDATE_URL)
        new_code = r.text
        r.close()

        with open("main.py", "w") as f:
            f.write(new_code)

        send_message("OTA: Update complete. Rebooting...")
        utime.sleep(2)
        machine.reset()

    except Exception as e:
        send_message("OTA: Failed to download update.")
        print("OTA error:", e)
        ota_updating = False

# =====================[ CORE 1: LED STATUS ONLY ]=====================

def core1_led_status():
    global core1_has_exited
    print("Core 1: LED status loop")
    wlan = network.WLAN(network.STA_IF)
    while not core1_should_stop:
        if wlan.isconnected():
            LED.value(1)
            utime.sleep(1)
        else:
            LED.toggle()
            utime.sleep(0.5)
    LED.value(0)
    core1_has_exited = True
    print("Core 1: LED loop exited")

# =====================[ COMMAND HANDLER ]=====================

def handle_command(cmd):
    global monitoring, mode
    if cmd == "/check":
        send_message(f"Digital reading: {digital.value()}")
    elif cmd == "/telemetry":
        send_message(get_telemetry())
    elif cmd == "/start":
        monitoring = True
        send_message("Monitoring resumed.")
    elif cmd == "/stop":
        monitoring = False
        send_message("Monitoring paused.")
    elif cmd == "/real":
        mode = "real"
        send_message("Mode set to /real.")
    elif cmd == "/test":
        mode = "test"
        send_message("Mode set to /test.")
    elif cmd == "/all":
        send_message("/telemetry     /check     /time     /start     /stop     /real     /test     /all     /update")
    elif cmd == "/time":
        t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
        send_message("Current time: {:02}:{:02} {:02}/{:02}/{:04}".format(t[3], t[4], t[2], t[1], t[0]))
    elif cmd.startswith("#") and len(cmd) == 13:
        try:
            hh = int(cmd[1:3])
            mm = int(cmd[3:5])
            dd = int(cmd[5:7])
            MM = int(cmd[7:9])
            yyyy = int(cmd[9:13])
            t = utime.mktime((yyyy, MM, dd, hh, mm, 0, 0, 0)) - TIMEZONE_OFFSET
            machine.RTC().datetime(utime.localtime(t)[:7] + (0,))
            send_message("Time set manually.")
        except:
            send_message("Invalid time format.")
    elif cmd == "/update":
        global core1_should_stop
        monitoring = False
        core1_should_stop = True
        send_message("Preparing OTA update...")
        while not core1_has_exited:
            utime.sleep(0.1)
        do_ota_update()

# =====================[ TELEGRAM LISTENER ]=====================

def listen_telegram():
    global last_update_id
    while True:
        if ota_updating:
            utime.sleep(1)
            continue
        updates = get_updates(last_update_id + 1 if last_update_id else None)
        for msg in updates:
            if "message" in msg and "text" in msg["message"]:
                txt = msg["message"]["text"]
                handle_command(txt)
                last_update_id = msg["update_id"]
                save_update_id(last_update_id)
                gc.collect()
        utime.sleep(2)

# =====================[ DIGITAL MONITORING ON CORE 0 ]=====================

def monitor_digital_sensor():
    while not ota_updating:
        if monitoring:
            value = digital.value()
            should_alert = (value == 1 if mode == "real" else value == 0)
            if should_alert:
                send_message("Sensor fault, check oxygen pump")
                for _ in range(30):
                    if ota_updating:
                        break
                    utime.sleep(1)
        utime.sleep(1)

# =====================[ MAIN ]=====================

def main():
    global core1_should_stop, core1_has_exited
    core1_should_stop = False
    core1_has_exited = False

    connect_wifi()
    sync_time()
    load_update_id()

    boot_msg = f"SEKATA Bioflok Monitoring System\nDevice Reboot and connected to Internet.\nVersion: {VERSION}\n/telemetry     /check     /time     /start     /stop     /real     /test     /all     /update"
    send_message(boot_msg)

    _thread.start_new_thread(core1_led_status, ())
    _thread.start_new_thread(monitor_digital_sensor, ())
    listen_telegram()

main()
