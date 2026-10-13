#!/usr/bin/env python3

import tkinter as tk
import threading
import math
import paho.mqtt.client as mqtt
from collections import deque

# ── Config ─────────────────────────────────────────────────────────────────
BROKER      = "localhost"
PORT        = 1883
TOPIC_CMD   = "home/vacuum/command"
TOPIC_SPEED = "home/vacuum/speed"
TOPIC_GOTO  = "home/vacuum/goto"
TOPICS      = [TOPIC_CMD, TOPIC_SPEED, TOPIC_GOTO]

# Canvas / room geometry
MAP_W,  MAP_H  = 660, 440   
MARGIN         = 30        
PANEL_W        = 220         
CANVAS_W       = MAP_W + PANEL_W
CANVAS_H       = MAP_H + MARGIN * 2

ROBOT_R        = 14       
SWEEP_STEP     = 34          
SPEED_VALUES   = {"SLOW": 1.0, "NORMAL": 2.2, "FAST": 4.2}

# Room bounding box 
RX1, RY1 = MARGIN,         MARGIN
RX2, RY2 = MARGIN + MAP_W, MARGIN + MAP_H

# Dock position 
DOCK_X, DOCK_Y = RX2 - 22, RY2 - 22

# Furniture obstacles — [x, y, w, h, label]
OBSTACLES = [
    [RX1 + 10,       RY1 + 10,        200, 65,  "SOFA"],
    [RX1 + 280,      RY1 + 10,        120, 90,  "DINING TABLE"],
    [RX2 - 90,       RY1 + 10,        70,  140, "BOOKSHELF"],
    [RX1 + 10,       RY2 - 80,        150, 65,  "CABINET"],
    [RX1 + 230,      RY2 - 70,        100, 60,  "SIDE TABLE"],
]

# ── Colour palette (LIDAR aesthetic) ───────────────────────────────────────
C = {
    "bg":           "#0a0e12",
    "floor_clean":  "#0c1f14",
    "wall":         "#00e87a",
    "wall_glow":    "#003d1f",
    "obs_fill":     "#0e1f12",
    "obs_border":   "#00c060",
    "obs_text":     "#006630",
    "robot":        "#d8e8dc",
    "robot_hi":     "#ff4444",
    "robot_dir":    "#0a0e12",
    "dock":         "#e8a020",
    "dock_ring":    "#3a2800",
    "beam":         "#00e87a",
    "grid":         "#0d1a10",
    "panel_bg":     "#06090c",
    "panel_border": "#1a3025",
    "text_hi":      "#00e87a",
    "text_lo":      "#2a5a3a",
    "text_warn":    "#ff4444",
    "text_amber":   "#e8a020",
    "text_white":   "#c8d8cc",
}

# ── Global state (protected by `state_lock`) ───────────────────────────────
state = {
    "mode":         "DOCKED",   # DOCKED|AUTO|PAUSED|STOPPED|RETURNING|GOTO
    "speed_name":   "NORMAL",
    "speed":        SPEED_VALUES["NORMAL"],
    "battery":      98,
    "x":            float(DOCK_X),
    "y":            float(DOCK_Y),
    "angle":        0.0,      
    "waypoints":    deque(),   
    "target":       None,       
    "last_cmd":     "—",
    "last_cmd_src": "device",  
    "hijacked":     False,
    "scan_angle":   0.0,       
    "cleaned":      [],        
    "log":          deque(maxlen=6),
    "battery_tick": 0,
}
state_lock = threading.Lock()


# ── Geometry helpers ────────────────────────────────────────────────────────
def in_obstacle(x, y, r=ROBOT_R):
    for ox, oy, ow, oh, _ in OBSTACLES:
        if (ox - r) < x < (ox + ow + r) and (oy - r) < y < (oy + oh + r):
            return True
    return False

def in_room(x, y, r=ROBOT_R):
    return RX1 + r < x < RX2 - r and RY1 + r < y < RY2 - r


# ── Path planning ───────────────────────────────────────────────────────────
def generate_sweep():
    wps = deque()
    y = RY1 + ROBOT_R + 10
    go_right = True
    while y < RY2 - ROBOT_R - 10:
        xs = (range(int(RX1 + ROBOT_R + 10), int(RX2 - ROBOT_R - 10), 18)
              if go_right else
              range(int(RX2 - ROBOT_R - 10), int(RX1 + ROBOT_R + 10), -18))
        prev_skip = False
        for x in xs:
            if in_room(x, y) and not in_obstacle(x, y):
                wps.append((float(x), float(y)))
                prev_skip = False
            else:
                if not prev_skip:
                    wps.append(None)   
                prev_skip = True
        y += SWEEP_STEP
        go_right = not go_right
    wps.append((float(DOCK_X), float(DOCK_Y)))
    return wps


# ── MQTT callbacks ──────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    for t in TOPICS:
        client.subscribe(t)

def on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode().strip().upper()
    with state_lock:
        state["hijacked"]     = True
        state["last_cmd"]     = f"{topic.split('/')[-1].upper()}: {payload}"
        state["last_cmd_src"] = "attacker"
        state["log"].appendleft(f"⚠ {payload}")

        if topic == TOPIC_CMD:
            if payload == "START":
                if state["mode"] in ("DOCKED", "STOPPED", "PAUSED"):
                    state["waypoints"] = generate_sweep()
                    state["target"]    = None
                    state["mode"]      = "AUTO"
            elif payload == "STOP":
                state["mode"]   = "STOPPED"
                state["target"] = None
            elif payload == "PAUSE":
                if state["mode"] == "AUTO":
                    state["mode"] = "PAUSED"
            elif payload == "RETURN_HOME":
                state["waypoints"] = deque([(float(DOCK_X), float(DOCK_Y))])
                state["target"]    = None
                state["mode"]      = "RETURNING"

        elif topic == TOPIC_SPEED:
            if payload in SPEED_VALUES:
                state["speed_name"] = payload
                state["speed"]      = SPEED_VALUES[payload]

        elif topic == TOPIC_GOTO:
            try:
                gx, gy = [float(v) for v in payload.split(",")]
                gx = max(RX1 + ROBOT_R, min(RX2 - ROBOT_R, gx))
                gy = max(RY1 + ROBOT_R, min(RY2 - ROBOT_R, gy))
                state["waypoints"] = deque([(gx, gy)])
                state["target"]    = None
                state["mode"]      = "GOTO"
            except Exception:
                pass


# ── Physics / movement update ───────────────────────────────────────────────
def update_robot():
    mode  = state["mode"]
    speed = state["speed"]
    x, y  = state["x"], state["y"]

    # Rotate LIDAR beams
    state["scan_angle"] = (state["scan_angle"] + 3.5) % 360

    # Battery drain
    state["battery_tick"] += 1
    if state["battery_tick"] >= 300 and state["battery"] > 1:
        state["battery"] -= 1
        state["battery_tick"] = 0

    if mode not in ("AUTO", "GOTO", "RETURNING"):
        return

    # Pick the next waypoint if we don't have a live target
    if state["target"] is None:
        while state["waypoints"]:
            nxt = state["waypoints"].popleft()
            if nxt is None:
                continue
            state["target"] = nxt
            break
        else:
            # Finished all waypoints
            if mode == "RETURNING":
                state["x"], state["y"] = float(DOCK_X), float(DOCK_Y)
                state["mode"] = "DOCKED"
                state["log"].appendleft("Returned to dock")
            elif mode == "AUTO":
                state["mode"] = "DOCKED"
                state["log"].appendleft("Clean cycle complete")
            elif mode == "GOTO":
                state["mode"] = "PAUSED"
            state["target"] = None
            return

    tx, ty = state["target"]
    dx, dy = tx - x, ty - y
    dist   = math.hypot(dx, dy)

    if dist < speed + 1:
        state["x"], state["y"] = tx, ty
        if mode == "AUTO":
            state["cleaned"].append((int(tx), int(ty)))
        state["target"] = None
    else:
        ratio = speed / dist
        nx, ny = x + dx * ratio, y + dy * ratio
        if in_room(nx, ny) and not in_obstacle(nx, ny):
            state["x"], state["y"] = nx, ny
            state["angle"] = math.degrees(math.atan2(dy, dx))
            if mode == "AUTO":
                state["cleaned"].append((int(nx), int(ny)))
        else:
            state["target"] = None   # obstacle in the way — skip this wp


# ── Dynamic rendering ───────────────────────────────────────────────────────
def redraw(canvas):
    canvas.delete("dynamic")

    # 1. Cleaned floor fill
    for cx, cy in state["cleaned"][::4]:   # sample every 4th for performance
        canvas.create_oval(cx - ROBOT_R, cy - ROBOT_R,
                           cx + ROBOT_R, cy + ROBOT_R,
                           fill=C["floor_clean"], outline="", tags="dynamic")

    # 2. LIDAR scan beams
    rx, ry  = state["x"], state["y"]
    sa      = state["scan_angle"]
    n_beams = 20
    for i in range(n_beams):
        a_deg = sa + (360 / n_beams) * i
        a_rad = math.radians(a_deg)
        ray_end = ROBOT_R + 2
        for ray_end in range(ROBOT_R + 2, 140, 3):
            bx = rx + math.cos(a_rad) * ray_end
            by = ry + math.sin(a_rad) * ray_end
            if not in_room(bx, by, 0) or in_obstacle(bx, by, 0):
                ray_end -= 3
                break
        bx = rx + math.cos(a_rad) * ray_end
        by = ry + math.sin(a_rad) * ray_end
        # Alternate: slightly brighter every 4th beam for "scan sweep" look
        beam_col = "#00ff88" if i % 4 == 0 else C["beam"]
        canvas.create_line(rx, ry, bx, by, fill=beam_col,
                           width=1, tags="dynamic")

    # 3. Robot body
    rob_col = C["robot_hi"] if state["hijacked"] else C["robot"]
    canvas.create_oval(rx - ROBOT_R, ry - ROBOT_R,
                       rx + ROBOT_R, ry + ROBOT_R,
                       fill=rob_col, outline=C["wall"], width=1,
                       tags="dynamic")
    # Direction dot
    a_rad = math.radians(state["angle"])
    ix = rx + math.cos(a_rad) * (ROBOT_R - 5)
    iy = ry + math.sin(a_rad) * (ROBOT_R - 5)
    canvas.create_oval(ix - 4, iy - 4, ix + 4, iy + 4,
                       fill=C["robot_dir"], outline="", tags="dynamic")

    # 4. Target crosshair
    if state["target"]:
        tx, ty = state["target"]
        s = 7
        canvas.create_line(tx - s, ty,     tx + s, ty,
                           fill=C["text_amber"], width=1, tags="dynamic")
        canvas.create_line(tx,     ty - s, tx,     ty + s,
                           fill=C["text_amber"], width=1, tags="dynamic")
        canvas.create_oval(tx - 3, ty - 3, tx + 3, ty + 3,
                           fill=C["text_amber"], outline="", tags="dynamic")

    # 5. Status panel
    px, py = MAP_W + MARGIN + 14, MARGIN

    hijacked = state["hijacked"]
    mode     = state["mode"]

    title_c = C["text_warn"] if hijacked else C["text_hi"]
    title_t = "⚠ HIJACKED" if hijacked else "SMART VACUUM"
    canvas.create_text(px, py, text=title_t, anchor="nw", fill=title_c,
                       font=("Courier", 13, "bold"), tags="dynamic")
    py += 22
    canvas.create_text(px, py, text="MODEL: RV-X9 PRO", anchor="nw",
                       fill=C["text_lo"], font=("Courier", 8), tags="dynamic")
    py += 18
    canvas.create_text(px, py, text="─" * 24, anchor="nw",
                       fill=C["panel_border"], font=("Courier", 8), tags="dynamic")
    py += 14

    def row(label, value, vc=None):
        nonlocal py
        vc = vc or C["text_white"]
        canvas.create_text(px, py, text=label, anchor="nw",
                           fill=C["text_lo"], font=("Courier", 9), tags="dynamic")
        canvas.create_text(px + 82, py, text=value, anchor="nw",
                           fill=vc, font=("Courier", 9, "bold"), tags="dynamic")
        py += 16

    mode_c = (C["text_warn"]  if mode in ("STOPPED",) else
              C["text_amber"] if mode in ("PAUSED", "RETURNING", "GOTO") else
              C["text_hi"])
    row("MODE",     mode,               mode_c)
    row("POS",      f"{int(state['x'])},{int(state['y'])}")
    spd_c = C["text_warn"] if state["speed_name"] == "FAST" else C["text_white"]
    row("SPEED",    state["speed_name"], spd_c)

    batt  = state["battery"]
    batt_c = (C["text_warn"]  if batt < 20 else
              C["text_amber"] if batt < 40 else C["text_hi"])
    bar   = "█" * (batt // 10) + "░" * (10 - batt // 10)
    row("BATTERY",  f"{batt}%", batt_c)
    canvas.create_text(px + 82, py - 2, text=bar[:10], anchor="nw",
                       fill=batt_c, font=("Courier", 8), tags="dynamic")
    py += 4

    covered = min(100, int(len(state["cleaned"]) / 900 * 100))
    row("COVERAGE", f"{covered}%",
        C["text_hi"] if covered > 80 else C["text_white"])

    py += 4
    canvas.create_text(px, py, text="─" * 24, anchor="nw",
                       fill=C["panel_border"], font=("Courier", 8), tags="dynamic")
    py += 14

    cmd_c = C["text_warn"] if state["last_cmd_src"] == "attacker" else C["text_lo"]
    canvas.create_text(px, py, text="LAST COMMAND", anchor="nw",
                       fill=C["text_lo"], font=("Courier", 8), tags="dynamic")
    py += 14
    canvas.create_text(px, py, text=state["last_cmd"][:26], anchor="nw",
                       fill=cmd_c, font=("Courier", 9, "bold"), tags="dynamic")
    py += 22

    canvas.create_text(px, py, text="─" * 24, anchor="nw",
                       fill=C["panel_border"], font=("Courier", 8), tags="dynamic")
    py += 14
    canvas.create_text(px, py, text="MQTT TOPICS", anchor="nw",
                       fill=C["text_lo"], font=("Courier", 8), tags="dynamic")
    py += 14
    for t in TOPICS:
        canvas.create_text(px, py,
                           text=f"  {t}", anchor="nw",
                           fill=C["text_lo"], font=("Courier", 8), tags="dynamic")
        py += 12

    py += 8
    canvas.create_text(px, py, text="─" * 24, anchor="nw",
                       fill=C["panel_border"], font=("Courier", 8), tags="dynamic")
    py += 14
    canvas.create_text(px, py, text="EVENT LOG", anchor="nw",
                       fill=C["text_lo"], font=("Courier", 8), tags="dynamic")
    py += 14
    for entry in list(state["log"]):
        canvas.create_text(px, py, text=entry[:26], anchor="nw",
                           fill=C["text_warn"] if "⚠" in entry else C["text_lo"],
                           font=("Courier", 8), tags="dynamic")
        py += 12


# ── Static scene (drawn once) ───────────────────────────────────────────────
def build_static(canvas):
    # Background
    canvas.create_rectangle(0, 0, CANVAS_W, CANVAS_H,
                             fill=C["bg"], outline="")
    # Subtle grid
    for gx in range(RX1, RX2, 40):
        canvas.create_line(gx, RY1, gx, RY2, fill=C["grid"], width=1)
    for gy in range(RY1, RY2, 40):
        canvas.create_line(RX1, gy, RX2, gy, fill=C["grid"], width=1)

    # Room walls with glow
    canvas.create_rectangle(RX1 - 4, RY1 - 4, RX2 + 4, RY2 + 4,
                             fill="", outline=C["wall_glow"], width=8)
    canvas.create_rectangle(RX1, RY1, RX2, RY2,
                             fill="", outline=C["wall"], width=2)

    # Furniture
    for ox, oy, ow, oh, label in OBSTACLES:
        canvas.create_rectangle(ox, oy, ox + ow, oy + oh,
                                 fill=C["obs_fill"],
                                 outline=C["obs_border"], width=1)
        canvas.create_text(ox + ow // 2, oy + oh // 2, text=label,
                           fill=C["obs_text"], font=("Courier", 7, "bold"))

    # Dock station
    canvas.create_rectangle(DOCK_X - 14, DOCK_Y - 14,
                             DOCK_X + 14, DOCK_Y + 14,
                             fill=C["dock_ring"], outline=C["dock"], width=2)
    canvas.create_text(DOCK_X, DOCK_Y + 22,
                       text="⌁ DOCK", fill=C["dock"], font=("Courier", 8, "bold"))

    # Panel background
    canvas.create_rectangle(MAP_W + MARGIN, 0, CANVAS_W, CANVAS_H,
                             fill=C["panel_bg"], outline=C["panel_border"], width=1)

    # Panel heading stripe
    canvas.create_rectangle(MAP_W + MARGIN, 0, CANVAS_W, 8,
                             fill=C["wall_glow"], outline="")


# ── Main loop ───────────────────────────────────────────────────────────────
def game_loop(canvas, root):
    with state_lock:
        update_robot()
        redraw(canvas)
    root.after(33, game_loop, canvas, root)   # ~30 fps


# ── Entry ────────────────────────────────────────────────────────────────────
def main():
    # Start auto-cleaning immediately so the audience sees the vacuum working
    with state_lock:
        state["waypoints"] = generate_sweep()
        state["mode"]      = "AUTO"
        state["x"]         = float(DOCK_X)
        state["y"]         = float(DOCK_Y)
        state["log"].appendleft("AUTO-CLEAN started")

    # MQTT
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER, PORT, 60)
        threading.Thread(target=client.loop_forever, daemon=True).start()
    except Exception as e:
        print(f"[warn] MQTT broker not reachable ({e}) — display-only mode")

    # GUI
    root = tk.Tk()
    root.title("Smart Vacuum — LIDAR Map View")
    root.resizable(False, False)
    root.config(bg=C["bg"])

    canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H,
                       bg=C["bg"], highlightthickness=0)
    canvas.pack()

    build_static(canvas)
    root.after(100, game_loop, canvas, root)
    root.mainloop()


if __name__ == "__main__":
    main()
