# IoT Environment Penetration Test — Initial Results

## 1. Host Discovery

### Command

```bash
nmap -sn 192.168.50.0/24 -oN 01-host-discovery.txt
```

### Output

```text
Starting Nmap 7.99 ( https://nmap.org ) at 2026-08-31 18:41 +1000
mass_dns: warning: Unable to determine any DNS servers. Reverse DNS is disabled. Try using --system-dns or specify valid servers with --dns-servers
Nmap scan report for 192.168.50.20
Host is up (0.00061s latency).
MAC Address: 00:0C:29:C4:2C:F0 (VMware)
Nmap scan report for 192.168.50.10
Host is up.
Nmap done: 256 IP addresses (2 hosts up) scanned in 8.69 seconds
```

### Result

Two hosts were identified on `192.168.50.0/24`:

| IP Address | Status | Notes |
|---|---|---|
| `192.168.50.10` | Up | Attacker/Kali VM |
| `192.168.50.20` | Up | IoT services/target VM |

---

## 2. Full Port and Service Enumeration

### Command

```bash
nmap -sV -sC -p- 192.168.50.20 -oN 02-iot-services.txt
```

### Output — Identified Services

```text
Nmap scan report for 192.168.50.20
Host is up (0.0013s latency).
Not shown: 65528 closed tcp ports (reset)

PORT     STATE SERVICE                 VERSION
1880/tcp open  vsat-control?
1883/tcp open  mosquitto version 2.1.2
1935/tcp open  rtmp?
8554/tcp open  http                    IDentifier NameTracer Pro httpd
8888/tcp open  http                    Golang net/http server
8889/tcp open  http                    Golang net/http server
8892/tcp open  ssl/http                Golang net/http server
```

Nmap identified the following additional information:

- `1880/tcp` returned an HTTP `200 OK` response and an OpenJS Foundation/Node-RED web interface.
- `1883/tcp` was identified as Mosquitto `2.1.2`.
- The MQTT NSE script was able to retrieve `$SYS` broker information, including:
  - `clients/active: 3`
  - `clients/connected: 3`
  - `clients/total: 5`
  - `subscriptions/count: 8`
  - `retained messages/count: 56`
  - `broker/version: mosquitto version 2.1.2`
- `8554/tcp`, `8888/tcp`, `8889/tcp`, and `8892/tcp` returned responses associated with MediaMTX.
- `8892/tcp` presented a TLS certificate with:
  - Subject: `commonName=mediamtx`
  - Not valid before: `2026-08-28T01:45:20`
  - Not valid after: `2036-08-25T01:45:20`
- Nmap reported several services as unrecognized despite receiving valid application responses.

### Nmap HTTP fingerprint for port 1880

The service returned:

```text
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 1731
...
```

The returned page contains the OpenJS Foundation copyright/licensing information associated with Node-RED.

### Nmap MediaMTX response

Ports `8888`, `8889`, and `8892` returned:

```text
Server: mediamtx
```

The HTTP probing also returned:

```text
HTTP/1.0 404 Not Found
Access-Control-Allow-Origin: *
Content-Type: text/plain
Server: mediamtx
...
page not found
```

The full Nmap output was retained in:

```text
02-iot-services.txt
```

---

## 3. Focused Service Enumeration

### Command

```bash
nmap -sV -p 1883,1880,8554 192.168.50.20
```

### Output

```text
Starting Nmap 7.99 ( https://nmap.org ) at 2026-08-31 18:43 +1000
mass_dns: warning: Unable to determine any DNS servers. Reverse DNS is disabled. Try using --system-dns or specify valid servers with --dns-servers
Nmap scan report for 192.168.50.20
Host is up (0.00077s latency).

PORT     STATE SERVICE                 VERSION
1880/tcp open  vsat-control?
1883/tcp open  mosquitto version 2.1.2
8554/tcp open  http                    IDentifier NameTracer Pro httpd
```

Nmap again recognised Mosquitto on `1883/tcp`, while `1880/tcp` and `8554/tcp` were not correctly identified by the service database.

---

## 4. MQTT Topic Enumeration

### Command

```bash
mosquitto_sub -h 192.168.50.20 -p 1883 -t '#' -v
```

### Output

No messages were displayed during the observation period.

The subscription was terminated with:

```text
^C
```

This command was useful for testing whether MQTT topics could be observed without supplying credentials.

---

## 5. MQTT Light Control — OFF

### Command

```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -p 1883 \
  -t home/livingroom/light/set \
  -m OFF
```

### Output

```text
home/livingroom/light/set OFF
```

The command successfully delivered the `OFF` message to the MQTT broker, and the simulated smart light responded.

---

## 6. MQTT Light Control — ON

### Command

```bash
mosquitto_pub \
  -h 192.168.50.20 \
  -p 1883 \
  -t home/livingroom/light/set \
  -m ON
```

### Output

```text
home/livingroom/light/set ON
```

The command successfully delivered the `ON` message to the MQTT broker, and the simulated smart light responded.

---

## 7. Network Interface Identification

The interface information was obtained with:

### Command

```bash
ip addr
```

### Relevant Output

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 00:0c:29:a7:65:35 brd ff:ff:ff:ff:ff:ff
    inet 192.168.50.10/24 brd 192.168.50.255 scope global noprefixroute eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::e406:4f77:38ce:3980/64 scope link noprefixroute
       valid_lft forever preferred_lft forever
```

The active IoT network interface was therefore confirmed as:

```text
eth0
192.168.50.10/24
```

---

## 8. MQTT Traffic Capture

### Command

```bash
sudo tcpdump -i eth0 -nn -A tcp port 1883
```

### Relevant Captured Traffic

The capture showed direct TCP communication between the attacker VM and MQTT broker:

```text
192.168.50.10.47960 > 192.168.50.20.1883
192.168.50.20.1883 > 192.168.50.10.47960
```

The MQTT protocol handshake was visible in the captured payload:

```text
MQTT
```

The captured traffic also exposed the application-level MQTT topic and payload:

```text
home/livingroom/light/setOFF
```

and later:

```text
home/livingroom/light/setON
```

A representative sequence was:

```text
18:58:21.112171 IP 192.168.50.10.47960 > 192.168.50.20.1883: Flags [P.], seq 1:15, ack 1, win 126, options [nop,nop,TS val 4056011000 ecr 4080954273], length 14
...
.....>k.....MQTT...<..
```

followed by:

```text
18:58:21.113499 IP 192.168.50.10.47960 > 192.168.50.20.1883: Flags [P.], seq 15:47, ack 5, win 126, options [nop,nop,TS val 4056011001 ecr 4080954276], length 32
...
.....>k.0...home/livingroom/light/setOFF
```

The subsequent `ON` command was also captured:

```text
18:58:25.093631 IP 192.168.50.10.36426 > 192.168.50.20.1883: Flags [P.], seq 15:46, ack 5, win 126, options [nop,nop,TS val 1346724095 ecr 443726891], length 31
...
PE\`..r.+0...home/livingroom/light/setON
```

The capture ended with:

```text
31 packets captured
31 packets received by filter
0 packets dropped by kernel
```

This demonstrates that MQTT application traffic on TCP/1883 is observable in plaintext on the test network.

---

## 9. RTSP Service Enumeration

### Command

```bash
nmap -sV -p 8554 192.168.50.20
```

### Output

```text
Starting Nmap 7.99 ( https://nmap.org ) at 2026-08-31 18:58 +1000
mass_dns: warning: Unable to determine any DNS servers. Reverse DNS is disabled. Try using --system-dns or specify valid servers with --dns-servers
Nmap scan report for 192.168.50.20
Host is up (0.00075s latency).

PORT     STATE SERVICE VERSION
8554/tcp open  http    IDentifier NameTracer Pro httpd
MAC Address: 00:0C:29:C4:2C:F0 (VMware)

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 11.56 seconds
```

Nmap did not correctly identify the service on `8554/tcp`, although subsequent RTSP testing confirmed that the port was serving the simulated camera stream.

---

## 10. RTSP Stream Identification

### Command

```bash
ffprobe \
  rtsp://admin:12345@192.168.50.20:8554/cam
```

### Relevant Output

```text
Input #0, rtsp, from 'rtsp://admin:12345@192.168.50.20:8554/cam':
  Metadata:
    title           : No Name
  Duration: N/A, start: 0.130431, bitrate: N/A
  Stream #0:0: Video: h264 (Main), yuv420p(tv, smpte170m/bt470bg/bt709, progressive), 640x360 [SAR 1:1 DAR 16:9], 30 fps, 30 tbr, 90k tbn, start 0.134767
  Stream #0:1: Audio: aac (LC), 44100 Hz, stereo, fltp, start 0.130431
```

The RTSP endpoint successfully returned:

- H.264 Main video
- Resolution: `640x360`
- Frame rate: `30 fps`
- AAC-LC audio
- Audio sample rate: `44100 Hz`
- Stereo audio

The stream was therefore accessible using the supplied RTSP credentials.

---

## 11. RTSP Stream Playback

### Command

```bash
ffplay \
  rtsp://admin:12345@192.168.50.20:8554/cam
```

### Relevant Output

```text
Input #0, rtsp, from 'rtsp://admin:12345@192.168.50.20:8554/cam':
  Metadata:
    title           : No Name
  Duration: N/A, start: 0.103356, bitrate: N/A
  Stream #0:0: Video: h264 (Main), yuv420p(tv, smpte170m/bt470bg/bt709, progressive), 640x360 [SAR 1:1 DAR 16:9], 30 fps, 30 tbr, 90k tbn, start 0.114267
  Stream #0:1: Audio: aac (LC), 44100 Hz, stereo, fltp, start 0.103356
```

The stream successfully opened in `ffplay`, confirming that the camera feed could be viewed from the attacker VM.

The playback was terminated with:

```text
^C
```

---

# Initial Findings

The testing performed so far demonstrates several significant properties of the simulated IoT environment:

| Finding | Evidence |
|---|---|
| IoT services are directly reachable from the attacker VM | Nmap host and port discovery |
| MQTT is exposed on TCP/1883 | `nmap -sV` |
| MQTT broker information can be queried | `$SYS` data returned by Nmap |
| MQTT commands can be published without credentials | `mosquitto_pub` successfully controlled the light |
| MQTT application traffic is visible in plaintext | `tcpdump` capture |
| Node-RED is exposed on TCP/1880 | HTTP response/OpenJS Foundation content |
| MediaMTX streaming services are exposed | Ports `8554`, `8888`, `8889`, `8892` |
| RTSP camera stream is accessible | `ffprobe` successfully identified the stream |
| Camera feed can be viewed remotely | `ffplay` successfully opened the stream |
| RTSP credentials are present in the connection URI | `admin:12345@192.168.50.20:8554/cam` |

## Current Test Scope

The testing completed in this phase covers:

1. Host discovery
2. Port and service enumeration
3. MQTT exposure testing
4. MQTT unauthenticated command publication
5. MQTT traffic capture
6. RTSP service identification
7. RTSP stream enumeration
8. RTSP stream playback

This is an initial evidence-gathering phase. Further testing can build on these confirmed attack paths rather than treating the services as theoretical vulnerabilities.

_Note: This sample attack was done before the lock device had been added to the enviroment as is therefore not referanced._