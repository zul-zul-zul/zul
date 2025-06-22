import network
import urequests
import utime as time
import machine
import ujson
import os
from secrets import WIFI_CREDENTIALS, BOT_TOKEN, CHAT_ID, GITHUB_TOKEN

VERSION = "v0.0.12b"
UPDATE_FLAG_FILE = "boot.flag"
LAST_UPDATE_ID_FILE = "update_id.txt"

led = machine.Pin("LED", machine.Pin.OUT)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for ssid, password in WIFI_CREDENTIALS.items():
        wlan.connect(ssid, password)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
        if wlan.isconnected():
            print(f"Connected to {ssid}")
            return True
    print("WiFi connection failed.")
    return False

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }
    try:
        response = urequests.post(url, json=payload)
        response.close()
    except:
        print("Failed to send Telegram message")

def safe_reboot():
    time.sleep(2)
    print("Rebooting via watchdog...")
    wdt = machine.WDT(timeout=1000)
    time.sleep(2)

def read_update_id():
    try:
        with open(LAST_UPDATE_ID_FILE, "r") as f:
            return int(f.read())
    except:
        return None

def write_update_id(update_id):
    with open(LAST_UPDATE_ID_FILE, "w") as f:
        f.write(str(update_id))

def parse_update_command(text):
    if text.startswith("#update="):
        return text.split("=", 1)[1].strip()
    return None

def handle_telegram():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
    last_update_id = read_update_id()

    if last_update_id:
        url += f"&offset={last_update_id + 1}"

    try:
        response = urequests.get(url)
        updates = response.json()["result"]
        response.close()
    except:
        print("Telegram poll failed")
        return

    for update in updates:
        if "message" not in update:
            continue
        text = update["message"].get("text", "")
        update_id = update["update_id"]

        print(f"Received: {text}")
        write_update_id(update_id)

        if text.startswith("/all"):
            send_telegram(
                "SEKATA Bioflok Monitoring System\n"
                f"Version: {VERSION}\n\n"
                "Available commands:\n"
                "/all     /read     /reset\n"
                "#update=https://link"
            )
        elif text.startswith("/read"):
            send_telegram("System running normally.")
        elif text.startswith("/reset"):
            send_telegram("Rebooting...")
            safe_reboot()
        elif text.startswith("#update="):
            link = parse_update_command(text)
            if link:
                send_telegram(f"OTA Update started from:\n{link}")
                ota_update(link)

def ota_update(link):
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = urequests.get(link, headers=headers)
        if response.status_code == 200:
            new_code = response.text
            with open("main_new.py", "w") as f:
                f.write(new_code)
                f.flush()
                if hasattr(os, "sync"):
                    os.sync()
            os.rename("main.py", "main_backup.py")
            os.rename("main_new.py", "main.py")
            send_telegram("✅ OTA Update successful. Rebooting...")
            with open(UPDATE_FLAG_FILE, "w") as f:
                f.write("reboot")
            safe_reboot()
        else:
            send_telegram("❌ OTA download failed.")
    except Exception as e:
        print("OTA error:", e)
        send_telegram("❌ OTA update error.")

def boot_check():
    if UPDATE_FLAG_FILE in os.listdir():
        try:
            os.remove(UPDATE_FLAG_FILE)
            send_telegram(f"✅ Rebooted successfully on {VERSION}")
        except:
            pass

def main():
    led.off()
    if connect_wifi():
        time.sleep(2)
        led.on()
        send_telegram(f"📶 Device rebooted.\nSEKATA Bioflok Monitoring System\nVersion: {VERSION}")
        boot_check()
        while True:
            handle_telegram()
            time.sleep(2)
    else:
        print("No WiFi. LED OFF")
        led.off()

main()
