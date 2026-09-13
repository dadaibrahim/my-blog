---
title: 'Auditing smart TV network and mic telemetry'
description: 'Concrete, reproducible steps for developers to audit smart TV network and microphone telemetry with captures, proxies, and local blocking.'
pubDate: 'Sep 13 2026'
heroImage: '../../assets/blog-placeholder-2.jpg'
---

Recent headlines about smart TV privacy can be useful prompts but they don’t replace hands-on verification. I spent a few weekends building a simple, repeatable workflow to see what a TV actually sends and when — network captures, DNS sinks, and a proxy for HTTP/S visibility. This is a dev-log style how-to: what I did, concrete commands, and the limitations you should expect.

## Setup an isolated test network

First rule: don’t test on someone else’s device or a production network. Create an isolated lab network so you can capture everything and, if needed, cut the device off from the internet.

- Use a spare router (OpenWrt, pfSense, or a home router with guest SSID) and put the TV on a guest SSID or VLAN.
- Run a DHCP server you control so you can set DNS and proxy options. If the TV allows manual proxy settings, put it there; otherwise use transparent interception on the gateway.
- Have at least two machines on the same network:
  - A capture host (Linux) with tcpdump/tshark/Wireshark.
  - A control host for DNS sinkholing (Pi-hole or dnsmasq) and for running a proxy (mitmproxy) if you need it.

If you only have one machine, you can create a hotspot or use a USB-Ethernet adapter to form the bridge.

## Capture traffic: tcpdump, tshark, and what to look for

Start with a full capture around the scenarios you want to test (idle, app open, voice command, firmware update attempt).

Example tcpdump to capture everything to a pcap file for a single device:

sudo tcpdump -i eth0 host 192.168.1.100 -w tv-test.pcap

Replace the interface and the device IP. If you want live filtering in text form, use tshark:

# list DNS requests from the device
sudo tshark -i eth0 -f "host 192.168.1.100 and udp port 53" -T fields -e dns.qry.name

# show TLS server names (SNI) for the device
sudo tshark -i eth0 -Y "ip.addr==192.168.1.100 and tls.handshake.extensions_server_name" -T fields -e tls.handshake.extensions_server_name

Important things to look for:
- DNS queries: hostnames tell you where the device is attempting to connect even if the connection is encrypted.
- TLS SNI and certificates: SNI reveals the server name for many TLS connections (unless ESNI/eSNI is used).
- Unencrypted HTTP and plain-text telemetry: search for JSON blobs, plain credentials, or endpoints.
- Periodic beacons: many devices keep a heartbeat; note frequency and destination.
- mDNS/SSDP/UPnP: service advertisements often reveal local APIs.

Use Wireshark to inspect flows visually; sort by endpoints and then by conversation to spot large uploads or persistent connections.

## Getting visibility into TLS traffic (and its limits)

Many connections will be encrypted. You can still get useful signals without breaking TLS:
- DNS hostnames
- TLS SNI
- IP ranges and timing patterns

If you control the device’s proxy settings, you can use mitmproxy to decrypt traffic (you’ll need to install the mitm CA into the device if it trusts user certs). For devices that don’t let you install a CA, you can set up a transparent proxy on the gateway, but that only works when the device doesn’t do certificate pinning.

Basic mitmproxy flow (if proxy is configurable):

1. Run mitmproxy on port 8080: mitmproxy -p 8080 --mode regular
2. Point the TV proxy to the capture host and do a test. Install mitmproxy CA cert if the TV's OS allows it.

If you can’t decrypt TLS, focus on DNS sinkholing and SNI analysis.

## Blocking and containment: Pi-hole, hosts, and iptables

Once you identify telemetry endpoints, you can block them locally. I use a combination of Pi-hole (DNS sinkhole) and firewall rules.

- Add known telemetry domains to Pi-hole’s blocklist or add static entries to its Local DNS records to redirect to 0.0.0.0.

Example /etc/hosts-style sinkhole lines (for your gateway resolver):

192.0.2.1 telemetry.example.com

- Use iptables (or nftables) on the gateway to drop or reject traffic to specific IPs or ports:

# block traffic to one destination IP for the TV
sudo iptables -I FORWARD -s 192.168.1.100 -d 203.0.113.45 -j REJECT

# redirect HTTP to a local web server
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080

Note: modifying network rules can break features (apps, firmware updates). Test carefully and keep a quick rollback plan.

## Quick script to log DNS queries in Python

If you want a simple programmatic way to watch DNS queries, this tiny script uses scapy to print queries from one IP:

```python
from scapy.all import sniff, DNSQR, IP

def dns_cb(pkt):
    if pkt.haslayer(DNSQR):
        q = pkt[DNSQR].qname.decode().rstrip('.')
        src = pkt[IP].src
        print(f"{src} queried {q}")

sniff(filter='udp port 53', prn=dns_cb, store=0)
```

Run it on the gateway; it gives immediate visibility into what hostnames the TV resolves.

## Mic and voice testing: a pragmatic approach

If you want to see whether voice activity causes outbound traffic, create controlled tests:
- Record a baseline capture with no voice activity.
- Trigger a voice command (and speak a short phrase), then capture for a minute after.
- Compare packet counts, destinations, and payload sizes. Look for burst uploads following the trigger. If traffic is encrypted, correlate timing with DNS/SNI to infer what subsystem handled it.

Note the legal and ethical constraint: record and analyze only devices you own or have explicit permission to test.

## Limitations and next steps

- Encrypted channels limit payload visibility; deeper inspection may require trusted CA installation or firmware extraction.
- Some devices do certificate pinning; those are much harder to MITM.
- For low-level proof (did the mic record?), the only robust path is firmware analysis or hardware access (serial, JTAG) — that’s a different, riskier discipline.

If you want to go further: extract the firmware and look for telemetry endpoints in strings/configs, or use a flash programmer to read storage — but only on hardware you own and with appropriate skills.

Wrap-up: networks give a lot of evidence even when traffic is encrypted. DNS, TLS SNI, timing, and packet sizes will tell you what a device is trying to do. Use isolated networks, consistent test cases, and simple tools (tcpdump, tshark, Pi-hole, mitmproxy) to build repeatable audits you can trust.