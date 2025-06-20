# main.py - v1.0.6
import network
import urequests
import utime
import machine
import _thread
import gc
import os
from machine import Pin, ADC

# === CONFIGURATION ===
VERSION = "v1.0.6"
WIFI_CREDENTIALS = {
    "Makers Studio": "Jba10600",
    "LorongGelap": "P@ssword.111"
}
BOT_TOKEN = "8050097491:AAEupepQid6h9-ch8NghIbuVeyZQxl6miE4"
CHAT_ID = "-1002725182243"
TIMEZONE_OFFSET = 8 * 3600  # GMT +8
GITHUB_URL = "https://raw.githubusercontent.com/zul-zul-zul/zul/refs/heads/main/main.py"

# === GLOBAL VARIABLES ===
monitoring = True
mode = "real"
last_alert_time = 0

# === HARDWARE ===
digital_pin = Pin(15, Pin.IN)
led = Pin("LED", Pin.OUT)

# === CONNECT TO WIFI ===
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        print(f"Trying Wi-Fi: {ssid}")
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                print("Connected to", ssid)
                return True
            utime.sleep(1)
    print("Failed to connect.")
    return False

# === SYNC TIME WITH NTP ===
def sync_time():
    import ntptime
    for _ in range(5):
        try:
            ntptime.settime()
            current = utime.time() + TIMEZONE_OFFSET
            tm = utime.localtime(current)
            print("NTP Time synced:", tm)
            return True
        except:
            print("NTP sync failed. Retrying...")
            utime.sleep(10)
    return False

# === TELEGRAM HELPERS ===
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message
        }
        response = urequests.post(url, json=data)
        response.close()
    except Exception as e:
        print("Telegram Error:", e)

# === OTA UPDATE (Only by /update command) ===
def ota_update():
    try:
        send_telegram("OTA: Downloading update...")
        response = urequests.get(GITHUB_URL)
        if response.status_code == 200:
            with open("main.py", "w") as f:
                f.write(response.text)
            response.close()
            send_telegram("OTA: Update successful. Rebooting...")
            utime.sleep(2)
            machine.reset()
        else:
            send_telegram(f"OTA: Failed with status {response.status_code}")
    except Exception as e:
        send_telegram("OTA: Error: " + str(e))

# === GET CPU TEMPERATURE ===
def get_cpu_temp():
    sensor_temp = ADC(4)
    reading = sensor_temp.read_u16()
    voltage = (reading / 65535) * 3.3
    temperature = 27 - (voltage - 0.706)/0.001721
    return round(temperature, 2)

# === GET TIME STRING ===
def get_time_string():
    t = utime.localtime(utime.time() + TIMEZONE_OFFSET)
    hour = t[3]
    am_pm = "am" if hour < 12 else "pm"
    hour_12 = hour if 1 <= hour <= 12 else abs(hour - 12)
    return f"{hour_12:02}:{t[4]:02} {am_pm} {t[2]:02}/{t[1]:02}/{t[0]}"

# === CORE 1 FUNCTION ===
def core1_thread():
    global last_alert_time
    while True:
        wlan = network.WLAN(network.STA_IF)
        internet = wlan.isconnected()
        led.value(internet)

        if monitoring:
            value = digital_pin.value()
            alert = False

            if mode == "real" and value == 1:
                alert = True
            elif mode == "test" and value == 0:
                alert = True

            if alert and utime.time() - last_alert_time >= 30:
                send_telegram("Sensor fault, check oxygen pump")
                last_alert_time = utime.time()

                # Blink during cooldown
                for _ in range(30):
                    led.toggle()
                    utime.sleep(0.5)

        utime.sleep(0.1)

# === TELEGRAM COMMAND HANDLER ===
def handle_command(cmd):
    global monitoring, mode
    if cmd == "/check":
        send_telegram(f"Digital Reading: {digital_pin.value()}")
    elif cmd == "/telemetry":
        send_telegram(f"Telemetry Data = {get_time_string()} - (Digital: {digital_pin.value()}) - CPU temp: {get_cpu_temp()}°C")
    elif cmd == "/time":
        send_telegram(f"Current Time: {get_time_string()}")
    elif cmd.startswith("#") and len(cmd) == 13:
        try:
            h, m, d, M, y = int(cmd[1:3]), int(cmd[3:5]), int(cmd[5:7]), int(cmd[7:9]), int(cmd[9:13])
            secs = utime.mktime((y, M, d, h, m, 0, 0, 0)) - TIMEZONE_OFFSET
            machine.RTC().datetime(utime.localtime(secs)[:7] + (0,))
            send_telegram("Time updated manually.")
        except:
            send_telegram("Invalid time format.")
    elif cmd == "/stop":
        monitoring = False
        send_telegram("Monitoring stopped.")
    elif cmd == "/start":
        monitoring = True
        send_telegram("Monitoring started.")
    elif cmd == "/real":
        mode = "real"
        send_telegram("Mode set to /real.")
    elif cmd == "/test":
        mode = "test"
        send_telegram("Mode set to /test.")
    elif cmd == "/all":
        send_telegram("/telemetry     /check     /time     /stop     /start     /real     /test     /update     /all")
    elif cmd == "/update":
        ota_update()

# === TELEGRAM POLLING LOOP ===
def telegram_loop():
    last_update = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update + 1}"
            response = urequests.get(url)
            data = response.json()
            response.close()

            for result in data["result"]:
                last_update = result["update_id"]
                message = result["message"]
                if "text" in message:
                    handle_command(message["text"])
            gc.collect()
        except Exception as e:
            print("Telegram loop error:", e)
        utime.sleep(1)

# === MAIN START ===
def main():
    connected = connect_wifi()
    if connected:
        sync_time()

    boot_msg = (
        "SEKATA Bioflok Monitoring System\n"
        "Device Reboot and connected to Internet.\n"
        f"Version: {VERSION}\n"
        "/telemetry     /check     /time     /stop     /start     /real     /test     /update     /all"
    )
    send_telegram(boot_msg)

    _thread.start_new_thread(core1_thread, ())
    telegram_loop()

main()
