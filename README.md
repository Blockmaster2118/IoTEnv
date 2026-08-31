# Virtualised IoT Penetration Testing Lab

A self-contained, isolated IoT security testing environment designed for demonstrating common IoT vulnerabilities and attack paths in a controlled virtualised network.

The lab uses intentionally vulnerable IoT services and simulated devices, including an RTSP camera, MQTT smart light, and BLE smart lock. Everything runs inside VMware and is isolated from real networks.

_(NOTE: The lock simulator is not yet implimented)_

## Architecture

| VM | OS | IP | Purpose |
|---|---|---|---|
| **Attacker** | Kali Linux | `192.168.50.10` | Penetration testing and analysis |
| **IoT Services** | Ubuntu Desktop 22.04 | `192.168.50.20` | RTSP camera, MQTT broker, Node-RED and smart-light simulator |
| **IoT Lock** | Debian 12 | `192.168.50.30` | Virtual BLE controllers and HackMeLock |

All VMs communicate through the isolated VMware LAN Segment:

```text
                    iotlab LAN Segment
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     Kali Linux       IoT Services       IoT Lock
    192.168.50.10     192.168.50.20     192.168.50.30
          │                │                │
       Attacker       RTSP / MQTT       BLE Lock
        Tools         Smart Light       Simulator
```

The lab network is intentionally isolated from the host's real LAN and the Internet.

## Components

### Attacker VM
Kali Linux provides the primary security testing environment, including:

- Nmap
- Wireshark
- Aircrack-ng
- Mosquitto clients
- VLC / FFmpeg
- BlueZ / GATTacker
- Other network analysis tools

### IoT Services VM
Ubuntu Desktop hosts the main IoT services using Docker:

- **MediaMTX** - simulated RTSP IP camera
- **Mosquitto** - deliberately insecure MQTT broker
- **Node-RED** - smart-home dashboard
- **Smart Light Simulator** - Python/Tkinter MQTT-controlled device

The camera feed and smart-light interface provide visible demonstrations of attacks against IoT services.

### IoT Lock VM
Debian hosts:

- Virtual Bluetooth HCI controllers
- HackMeLock BLE smart-lock simulator
- GATTacker for BLE security testing

No physical Bluetooth hardware is required.

## Network Setup

Create a VMware **LAN Segment** named:

```text
iotlab
```

Assign the LAN Segment to all three VMs and configure the static addresses shown above.

During initial installation, a temporary **NAT adapter** may be added to download packages and dependencies. Once setup is complete, remove the NAT adapter so the lab remains isolated.

## Running the Lab

On the IoT Services VM:

```bash
cd ~/iot-lab
docker compose up -d

python3 ~/iot-lab/smart_light.py &
ffplay -rtsp_transport tcp rtsp://127.0.0.1:8554/cam
```

The Docker stack provides the RTSP and MQTT services, while the smart-light simulator provides a visible MQTT-controlled device.

## Verification

From the Kali VM:

```bash
nmap -sn 192.168.50.0/24

nmap -sV -p 8554,1883,1880 192.168.50.20

mosquitto_sub -h 192.168.50.20 -t '#' -v

ffprobe rtsp://admin:12345@192.168.50.20:8554/cam
```

The expected hosts are:

```text
192.168.50.20  IoT Services
192.168.50.30  IoT Lock
```

Successful host discovery and service checks indicate that the lab is ready for penetration-testing exercises.

## Attack Commands

From the first sample attack, the successful attack commands are:

Smart Light:
```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -p 1883 \
  -t home/livingroom/light/set \
  -m OFF
```

_Note: the payload ('OFF') can be changed to turn the light on or change it's colour (either simple colours or hex codes)_

Security Camera:
```bash
ffplay \
  rtsp://admin:12345@192.168.50.20:8554/cam
```

## Credentials

The precreated VM credentials. _Both users have ```sudo``` on respective machinces_

Attacker:
```
Username: attacker
Password: attacker
```

Target:
```
Username: target
Password: target
```