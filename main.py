# SEKATA Bioflok Monitoring System
# Version: v1.0.3

import network
import urequests
import utime
import machine
import _thread
import ntptime
import gc

# ==== CONFIGURATION ====
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}

BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
NTP_RETRIES = 5
VERSION = "v1.0.3"
TIMEZONE_OFFSET = 8 * 3600  # GMT+8
GITHUB_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/main/main.py"

# ==== GLOBAL STATE ====
digital_pin = machine.Pin(15, machine.Pin.IN)
led = machine.Pin("LED", machine.Pin.OUT)
monitoring_enabled = True
mode = "real"

# ==== CONNECT TO WIFI ====
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, pwd in WIFI_CREDENTIALS.items():
        print(f"Trying Wi-Fi: {ssid}")
        wlan.connect(ssid, pwd)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected to Wi-Fi")
                return True
            utime.sleep(1)
    print("Failed to connect to Wi-Fi.")
    return False

# ==== SYNC TIME ====
def sync_time():
    for _ in range(NTP_RETRIES):
        try:
            ntptime.settime()
            utime.sleep(1)
            print("Time synced via NTP.")
            return True
        except:
            print("Retrying NTP...")
            utime.sleep(10)
    print("NTP sync failed.")
    return False

# ==== GET TIME STRING ====
def get_time_str():
    t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
    return "{:02d}:{:02d} {} {:02d}/{:02d}/{}".format(
        (t[3] % 12) or 12, t[4], "am" if t[3] < 12 else "pm", t[2], t[1], t[0]
    )

# ==== TELEGRAM MESSAGE ====
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        response = urequests.post(url, json=payload)
        response.close()
    except Exception as e:
        print("Telegram send failed:", e)

# ==== OTA UPDATE ====
def ota_update():
    try:
        send_telegram("OTA: Downloading update...")
        response = urequests.get(GITHUB_URL)
        if response.status_code == 200:
            with open("main.py", "w") as f:
                f.write(response.text)
            response.close()
            send_telegram("Update to v1.0.3 successful. Rebooting.")
            utime.sleep(2)
            machine.reset()
        else:
            send_telegram("OTA: Failed to download update.")
    except Exception as e:
        send_telegram(f"OTA: Error: {str(e)}")

# ==== HANDLE COMMAND ====
def handle_command(cmd):
    global monitoring_enabled, mode
    if cmd == "/telemetry":
        msg = f"Telemetry Data = {get_time_str()} - (Digital: {digital_pin.value()}) - CPU temp: {read_cpu_temp():.2f}°C"
        send_telegram(msg)
    elif cmd == "/check":
        send_telegram(f"Digital Reading: {digital_pin.value()}")
    elif cmd == "/time":
        send_telegram(f"Current Time: {get_time_str()}")
    elif cmd.startswith("#"):
        try:
            hh = int(cmd[1:3])
            mm = int(cmd[3:5])
            dd = int(cmd[5:7])
            MM = int(cmd[7:9])
            yyyy = int(cmd[9:13])
            t = utime.mktime((yyyy, MM, dd, hh, mm, 0, 0, 0))
            machine.RTC().datetime(utime.localtime(t - TIMEZONE_OFFSET))
            send_telegram("Time manually set.")
        except:
            send_telegram("Invalid time format.")
    elif cmd == "/stop":
        monitoring_enabled = False
        send_telegram("Monitoring paused.")
    elif cmd == "/start":
        monitoring_enabled = True
        send_telegram("Monitoring resumed.")
    elif cmd == "/real":
        mode = "real"
        send_telegram("Mode set to REAL.")
    elif cmd == "/test":
        mode = "test"
        send_telegram("Mode set to TEST.")
    elif cmd == "/all":
        send_telegram("/telemetry     /check     /time     /stop     /start     /real     /test     /update     /all")
    elif cmd == "/update":
        send_telegram("Starting OTA update...")
        ota_update()

# ==== READ CPU TEMP ====
def read_cpu_temp():
    sensor_temp = machine.ADC(4)
    voltage = sensor_temp.read_u16() * 3.3 / 65535
    return 27 - (voltage - 0.706) / 0.001721

# ==== CORE 1: MONITORING ====
def core1_loop():
    global monitoring_enabled
    while True:
        wlan = network.WLAN(network.STA_IF)
        led.value(wlan.isconnected())

        if not monitoring_enabled:
            utime.sleep(1)
            continue

        value = digital_pin.value()
        trigger = False

        if mode == "real" and value == 1:
            trigger = True
        elif mode == "test" and value == 0:
            trigger = True

        if trigger:
            send_telegram("Sensor fault, check oxygen pump")
            for _ in range(30):
                led.toggle()
                utime.sleep(0.5)
            led.value(wlan.isconnected())
        else:
            utime.sleep(1)

# ==== CORE 0: TELEGRAM HANDLER ====
def telegram_loop():
    last_hour = -1
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10&offset={last_update_id + 1}"
            res = urequests.get(url)
            data = res.json()
            res.close()

            for result in data["result"]:
                last_update_id = result["update_id"]
                msg = result["message"]
                text = msg.get("text", "")
                handle_command(text)

            now = utime.localtime(utime.time() + TIMEZONE_OFFSET)
            if now[4] == 0 and now[3] != last_hour:
                last_hour = now[3]
                send_telegram(f"Telemetry Data = {get_time_str()} - (Digital: {digital_pin.value()}) - CPU temp: {read_cpu_temp():.2f}°C")

            gc.collect()
        except Exception as e:
            print("Telegram error:", e)
            utime.sleep(5)

# ==== MAIN BOOT ====
def main():
    if connect_wifi():
        if sync_time():
            boot_msg = (
                f"SEKATA Bioflok Monitoring System\n"
                f"Device Reboot and connected to Internet.\n"
                f"Version: {VERSION}\n"
                f"/telemetry     /check     /time     /stop     /start     /real     /test     /update     /all"
            )
            send_telegram(boot_msg)

    _thread.start_new_thread(core1_loop, ())
    telegram_loop()

main()
