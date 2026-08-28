#!/usr/bin/env python3
#
# Visual "smart light" simulator.
# Subscribes to home/livingroom/light/set  (payload: ON / OFF / <hex colour>)

import tkinter as tk
import threading
import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC  = "home/livingroom/light/set"

# ── initial state ──────────────────────────────────────────────────────────
state = {"on": True, "colour": "#FFD700"}  

def set_light(on: bool, colour: str = None):
    state["on"] = on
    if colour:
        state["colour"] = colour
    bg   = state["colour"] if on else "#1a1a1a"
    text = f"💡  LIGHT  {'ON' if on else 'OFF'}"
    bulb_label.config(bg=bg, text=text,
                      fg="black" if on else "#555555")
    root.config(bg=bg)
    status_label.config(
        text=f"Topic: {TOPIC}\nLast command: {'ON' if on else 'OFF'}",
        bg=bg, fg="black" if on else "#555555")

# ── MQTT callbacks ─────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip().upper()
    if payload == "ON":
        root.after(0, set_light, True)
    elif payload == "OFF":
        root.after(0, set_light, False)
    elif payload.startswith("#"):                  
        root.after(0, set_light, True, payload)
    elif payload == "RED":
        root.after(0, set_light, True, "#FF2200")
    elif payload == "BLUE":
        root.after(0, set_light, True, "#0044FF")
    elif payload == "GREEN":
        root.after(0, set_light, True, "#00CC44")

# ── GUI ────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("Smart Light — Living Room")
root.geometry("400x300")
root.resizable(False, False)

bulb_label = tk.Label(root, text="💡  LIGHT  ON",
                      font=("Helvetica", 32, "bold"),
                      padx=20, pady=60)
bulb_label.pack(fill="both", expand=True)

status_label = tk.Label(root,
                        text=f"Topic: {TOPIC}\nLast command: —",
                        font=("Helvetica", 10), pady=6)
status_label.pack()

set_light(True)   

# ── MQTT thread ────────────────────────────────────────────────────────────
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, 1883, 60)
threading.Thread(target=client.loop_forever, daemon=True).start()

root.mainloop()