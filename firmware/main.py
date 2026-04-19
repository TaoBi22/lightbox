#!/usr/bin/env python3
import serial
import spidev
import smbus2
import time
import threading

# --- DMX setup ---
dmx = serial.Serial('/dev/ttyAMA0', baudrate=250000, bytesize=8, stopbits=2)

current_dmx = [0] * 512
current_dmx[0] = 255  # Intensity always full
dmx_lock = threading.Lock()

def send_dmx(channels):
    data = [0x00] + list(channels) + [0x00] * (512 - len(channels))
    dmx.break_condition = True
    time.sleep(120 / 1000000.0)
    dmx.break_condition = False
    time.sleep(12 / 1000000.0)
    dmx.write(bytearray(data))

def dmx_thread():
    while True:
        with dmx_lock:
            channels = list(current_dmx)
        send_dmx(channels)

def set_colour(r, g, b):
    with dmx_lock:
        current_dmx[0] = 255  # Intensity
        current_dmx[1] = r
        current_dmx[2] = g
        current_dmx[3] = b

# --- APA102 LED setup (SPI) ---
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 4096000
spi.mode = 0b00

def set_leds(colours):
    buf = [0x00] * 4
    for r, g, b in colours:
        buf += [0xFF, b, g, r]
    buf += [0xFF] * 4
    spi.xfer2(buf)

def clear_leds():
    set_leds([(0, 0, 0)] * 16)

# --- TCA9555 button setup (I2C) ---
bus = smbus2.SMBus(1)
TCA9555_ADDR = 0x20

def read_buttons():
    low  = bus.read_byte_data(TCA9555_ADDR, 0x00)
    high = bus.read_byte_data(TCA9555_ADDR, 0x01)
    raw = low | (high << 8)
    return [not bool(raw & (1 << i)) for i in range(16)]

# --- Key layout ---
KEY_RED   = 0
KEY_GREEN = 1
KEY_BLUE  = 2

KEY_COLOURS = {
    KEY_RED:   (255, 0,   0),
    KEY_GREEN: (0,   255, 0),
    KEY_BLUE:  (0,   0,   255),
}

# Initialise keypad LEDs
leds = [(0, 0, 0)] * 16
for key, colour in KEY_COLOURS.items():
    leds[key] = colour
set_leds(leds)

# Start with red
set_colour(255, 0, 0)

# Start DMX thread
t = threading.Thread(target=dmx_thread, daemon=True)
t.start()

prev_buttons = [False] * 16
last_press = {}

print("Ready! Press red, green or blue key to change colour. Ctrl+C to exit.")

try:
    while True:
        buttons = read_buttons()
        now = time.time()

        for key, (r, g, b) in KEY_COLOURS.items():
            if buttons[key] and not prev_buttons[key]:
                if now - last_press.get(key, 0) > 0.2:
                    last_press[key] = now
                    set_colour(r, g, b)
                    print(f"Colour set to {'red' if key == KEY_RED else 'green' if key == KEY_GREEN else 'blue'}")

        prev_buttons = buttons
        time.sleep(0.02)

except KeyboardInterrupt:
    print("Exiting...")
    set_colour(0, 0, 0)
    time.sleep(0.1)
    clear_leds()
    dmx.close()
    spi.close()
    bus.close()
