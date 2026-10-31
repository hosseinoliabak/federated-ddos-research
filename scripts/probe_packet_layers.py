# /// script
# requires-python = ">=3.11"
# dependencies = ["scapy==2.5.0"]
# ///
"""Demonstrate field-scope ambiguity offline; this does not identify a dataset extractor.

Run with: uv run --script scripts/probe_packet_layers.py
Only synthetic packet objects are constructed and decoded. No packets are sent,
no interfaces are captured, and no external dataset is read.
"""

import json
import platform

import scapy
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import CookedLinux, Ether


def probe():
    ip = IP(src="192.0.2.1", dst="192.0.2.2", flags=0)
    ethernet = Ether(src="02:00:00:00:00:01", dst="02:00:00:00:00:02")
    cooked = CookedLinux(proto=0x0800)
    fixtures = [
        ("ethernet_tcp_syn", ethernet / ip / TCP(sport=12345, dport=443, flags="S")),
        ("cooked_tcp_syn", cooked / ip / TCP(sport=12345, dport=443, flags="S")),
        ("cooked_udp", cooked / ip / UDP(sport=12345, dport=443)),
        (
            "ethernet_ipv4_mf_tcp_syn",
            ethernet
            / IP(src="192.0.2.1", dst="192.0.2.2", flags="MF")
            / TCP(sport=12345, dport=443, flags="S"),
        ),
    ]
    rows = []
    for name, original in fixtures:
        # Round-trip bytes so the check covers layer dissection as well as construction.
        packet = type(original)(bytes(original))
        rows.append(
            dict(
                case=name,
                unscoped_protocol=int(packet.proto),
                ipv4_protocol=int(packet[IP].proto),
                unscoped_flags=str(packet.flags),
                tcp_flags=str(packet[TCP].flags) if TCP in packet else None,
                unscoped_syn_test="S" in str(packet.flags),
                unscoped_fin_test="F" in str(packet.flags),
                tcp_syn_test=bool(int(packet[TCP].flags) & 0x02) if TCP in packet else None,
                tcp_fin_test=bool(int(packet[TCP].flags) & 0x01) if TCP in packet else None,
            )
        )
    expected = [
        (6, 6, "", "S", False, False, True, False),
        (2048, 6, "", "S", False, False, True, False),
        (2048, 17, "", None, False, False, None, None),
        (6, 6, "MF", "S", False, True, True, False),
    ]
    for row, target in zip(rows, expected):
        actual = tuple(value for key, value in row.items() if key != "case")
        if actual != target:
            raise RuntimeError(f"Synthetic layer check failed for {row['case']}: {actual}")
    return dict(
        schema=1,
        purpose="synthetic_layer_access_regression_only",
        python=platform.python_version(),
        scapy=scapy.__version__,
        fixtures=rows,
        checks_passed=len(rows),
        network_packets_sent=0,
        real_dataset_read=False,
        limit="A possible parsing mechanism, not proof of any dataset's extractor or defects.",
    )


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
