#!/usr/bin/env python3
# ~/iot-lab/lock_client.py

import socket, sys, time

HOST         = "localhost"
PORT         = 9999
UNLOCK_TOKEN = "UNLOCK:1234"
LOCK_TOKEN   = "LOCK:1234"

def send_command(cmd):
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        print(f"[>] Connecting to {HOST}:{PORT} (simulated BLE GATT write)")
        print(f"[>] Sending payload: {cmd!r}")
        s.sendall((cmd + "\n").encode())
        response = s.recv(256).decode().strip()
        print(f"[<] Lock response:   {response}")

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "unlock"
    cmd = UNLOCK_TOKEN if action == "unlock" else LOCK_TOKEN
    send_command(cmd)
