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
        wlan.conne
