#!/usr/bin/env python3
# ~/iot-lab/smart_lock.py

import tkinter as tk
import threading
import socket
import time
from collections import deque

# ── Config ─────────────────────────────────────────────────────────────────
HOST         = "0.0.0.0"
PORT         = 9999
UNLOCK_TOKEN = "UNLOCK:1234" 
LOCK_TOKEN   = "LOCK:1234"
DEVICE_NAME  = "SmartLock-X1 Pro"

# ── State ──────────────────────────────────────────────────────────────────
state = {
    "locked":      True,
    "last_cmd":    "-",
    "last_src":    "-",
    "total_cmds":  0,
    "hijacked":    False,
    "log":         deque(maxlen=7),
}
state_lock = threading.Lock()

# ── Colour palette ─────────────────────────────────────────────────────────
C = {
    "bg_locked":    "#120000",
    "bg_unlocked":  "#001208",
    "locked":       "#ff3333",
    "unlocked":     "#00e066",
    "amber":        "#e8a020",
    "text_dim":     "#445544",
    "text_white":   "#b8c8b8",
    "text_warn":    "#ff4444",
    "panel":        "#080c08",
    "panel_border": "#1a2e1a",
}

# ── TCP server (simulates BLE GATT characteristic writes) ──────────────────
def handle_client(conn, addr):
    src_ip = addr[0]
    try:
        data = conn.recv(256).decode().strip()
        if not data:
            return

        with state_lock:
            state["total_cmds"] += 1
            state["last_src"]   = src_ip
            state["last_cmd"]   = data

            is_local = src_ip in ("127.0.0.1", "::1")
            if not is_local:
                state["hijacked"] = True

            tag = "[DEVICE]" if is_local else "[ATTACKER]"

            if data == UNLOCK_TOKEN:
                state["locked"] = False
                state["log"].appendleft(f"{tag} UNLOCK — door open")
                conn.sendall(b"OK:UNLOCKED\n")
            elif data == LOCK_TOKEN:
                state["locked"] = True
                state["log"].appendleft(f"{tag} LOCK — door secured")
                conn.sendall(b"OK:LOCKED\n")
            else:
                state["log"].appendleft(f"{tag} UNKNOWN: {data[:24]}")
                conn.sendall(b"ERR:UNKNOWN_COMMAND\n")
    except Exception as e:
        pass
    finally:
        conn.close()

def tcp_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(5)
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr),
                             daemon=True).start()

# ── Drawing ────────────────────────────────────────────────────────────────
def draw_padlock(canvas, locked, colour, cx, cy):
    # No canvas.delete here — redraw() wipes "frame" before calling this

    bw, bh = 80, 70
    bx1 = cx - bw // 2
    by1 = cy - 10
    bx2 = cx + bw // 2
    by2 = cy + bh

    # Body
    canvas.create_rectangle(bx1, by1, bx2, by2,
                             fill=colour, outline=colour,
                             width=0, tags="frame")
    # Keyhole circle
    canvas.create_oval(cx - 12, by1 + 18, cx + 12, by1 + 42,
                       fill=C["bg_locked"] if locked else C["bg_unlocked"],
                       outline="", tags="frame")
    # Keyhole slot
    canvas.create_rectangle(cx - 5, by1 + 34, cx + 5, by1 + 54,
                             fill=C["bg_locked"] if locked else C["bg_unlocked"],
                             outline="", tags="frame")

    sw = 44
    sh = 50
    sx1 = cx - sw // 2
    sy1 = cy - sh - 14
    sx2 = cx + sw // 2
    sy2 = cy - 10

    if locked:
        # Shackle fully closed
        canvas.create_arc(sx1, sy1, sx2, sy2 + 20,
                          start=0, extent=180,
                          style="arc", outline=colour,
                          width=14, tags="frame")
    else:
        # Shackle open
        canvas.create_arc(sx1, sy1 - 24, sx2, sy2 - 4,
                          start=0, extent=180,
                          style="arc", outline=colour,
                          width=14, tags="frame")
        # Left leg still in body
        canvas.create_line(sx1 + 7, cy - 10, sx1 + 7, cy + 4,
                           fill=colour, width=14,
                           capstyle="round", tags="frame")

def redraw(canvas, root):
    # Reschedule FIRST — drawing errors below will never kill the loop
    root.after(80, redraw, canvas, root)

    try:
        with state_lock:
            locked   = state["locked"]
            hijacked = state["hijacked"]
            last_cmd = state["last_cmd"]
            last_src = state["last_src"]
            log      = list(state["log"])
            total    = state["total_cmds"]

        bg     = C["bg_locked"] if locked else C["bg_unlocked"]
        colour = C["locked"] if locked else C["unlocked"]
        status = "LOCKED" if locked else "UNLOCKED"

        W = int(canvas["width"])
        H = int(canvas["height"])
        cx = W // 2
        cy = H // 2 - 35

        # Wipe every item from the previous frame (single tag covers everything)
        canvas.delete("frame")

        canvas.create_rectangle(0, 0, W, H,
                                 fill=bg, outline="", tags="frame")

        glow_cy = cy + 25
        for r in range(60, 0, -10):
            canvas.create_oval(cx - r, glow_cy - r, cx + r, glow_cy + r,
                               outline=colour if r < 40 else bg,
                               width=1, tags="frame")

        draw_padlock(canvas, locked, colour, cx, cy)

        # Device title
        title_c = C["text_warn"] if hijacked else colour
        title_t = f"⚠  {DEVICE_NAME}" if hijacked else DEVICE_NAME
        canvas.create_text(
            W // 2, 55,
            text=title_t,
            fill=title_c,
            font=("Courier", 13, "bold"),
            tags="frame"
        )

        # Lock status
        canvas.create_text(
            W // 2, 390,
            text=status,
            fill=colour,
            font=("Courier", 26, "bold"),
            tags="frame"
        )

        # Hijack note
        hijack_note = (
            "UNDER ATTACKER CONTROL"
            if hijacked else "Normal operation"
        )
        canvas.create_text(
            W // 2, 425,
            text=hijack_note,
            fill=C["text_warn"] if hijacked else C["text_dim"],
            font=("Courier", 10),
            tags="frame"
        )

    except Exception as e:
        print(f"[redraw] error: {e}")


def main():
    with state_lock:
        state["log"].appendleft("[DEVICE] Lock armed — awaiting commands")

    threading.Thread(target=tcp_server, daemon=True).start()

    root = tk.Tk()
    root.title(f"Smart Lock — {DEVICE_NAME}")
    root.resizable(False, False)

    W, H = 500, 500
    canvas = tk.Canvas(
        root,
        width=W,
        height=H,
        bg=C["bg_locked"],
        highlightthickness=0
    )
    canvas.pack()

    root.after(100, redraw, canvas, root)   
    root.mainloop()


if __name__ == "__main__":
    main()