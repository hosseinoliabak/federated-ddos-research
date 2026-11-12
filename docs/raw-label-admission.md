# Conservative packet and source-label admission

This checker asks whether source connection labels can be associated with a
saved capture without guessing connection ends or resolving tuple reuse by
record order. The output is an engineering admission audit. It is not a model
experiment, a benchmark acceptance or a reconstruction of physical attack
episodes.

The committed `raw-label-policy-v1.json` defines the procedure before an actual
audit. The checker reads complete unfragmented Ethernet/IPv4 TCP and UDP
packets, preserves original record order and compares exact integer
microsecond timestamps. It uses the original Zeek originator/responder tuple
and its reverse. A packet is only a candidate when its tuple and source time
interval agree. A unique candidate becomes an admitted association only after
the whole source connection has matching directional packet counts, IP-byte
counts and endpoints in time. Competing candidates remain ambiguous, even
when they have the same class.

An unset duration is not an invalid record. When the source counters describe
one packet, an exact point match can be checked. The checker does not invent
an end for an unset multi-packet duration. Known TCP durations also need care:
Zeek documentation explains that they can omit trailing non-productive TCP
packets. The policy therefore never extends a duration to collect additional
packets. Any resulting incomplete connection remains unreconciled.

Original connection labels and regenerated timeout-flow labels serve different
roles. The diagnostic meter receives every supported packet, including packets
without an admitted binary label and packets in other attack categories. A new
record receives a binary label only when all of its retained packets have
admitted source associations with the same binary class. C&C and scanning
remain outside DDoS-versus-benign. A mixed or unknown record is counted rather
than removed before metering. The fixed sampling/timeout grid describes label
coverage and record boundaries only. It supplies no model score or evidence of
live extractor equivalence.

The independent installed libpcap reader must reproduce the complete record
stream, including each timestamp, captured length, wire length and packet
bytes. Installed tcpdump separately decodes numeric directional tuples and
timestamps for all policy-supported packets. Both tools operate offline; the
checker performs no DNS lookup, capture, replay or network request. Neither
reader supplies independent ground truth for analyst labels.

Run with a private sealed input contract. The contract names the originals,
their hashes, the exact clean code commit, the source and policy hashes, and
the dependency lock. Runtime paths must remain in `FDDOS_WORKSPACE`; the
originals must be mode0444. The output directory must be new. Results retain
only aggregate statistics and packet/source-row ordinals, not packet payloads
or endpoint rows. Do not commit runtime inputs or outputs.

```sh
FDDOS_WORKSPACE=/private/research-workspace python scripts/raw_label_admission.py \
  --contract /private/research-workspace/reports/input-contract.json \
  --contract-sha256 EXACT_CONTRACT_SHA256 \
  --output /private/research-workspace/reports/new-admission-run
```

Source evidence was checked before the policy was written. The IoT-23 author
page, “Labeling process” and “Summary of the datasets,” describes analyst
rules applied to Zeek connection logs, rather than independently recorded
packet attack boundaries. Current `Conn::Info` documentation identifies the
first packet, optional duration and directional IP counters. The historical
Zeekv2.6.1 source also assigns duration only when positive while allowing
packet counters without it. This historical implementation is a comparative
reference; the source capture does not establish that exact installed version
or configuration. RFC791 Section3.1 defines IPv4 IHL, total length, protocol
and fragmentation fields. RFC768 defines the UDP header; RFC9293 Section3.1
defines the TCP header. The installed-tool comparisons use the versioned
libpcap savefile description and tcpdump offline-read documentation.

Primary references consulted:

- [IoT-23 author description](https://www.stratosphereips.org/datasets-iot23)
- [Zeek Conn::Info](https://docs.zeek.org/en/current/scripts/base/protocols/conn/main.zeek.html)
- [Zeekv2.6.1 connection logging, lines14–28 and214–229](https://github.com/zeek/zeek/blob/v2.6.1/scripts/base/protocols/conn/main.bro#L14)
- [IPv4 RFC791 Section3.1](https://www.rfc-editor.org/rfc/rfc791.html#section-3.1)
- [UDP RFC768](https://www.rfc-editor.org/rfc/rfc768.html)
- [TCP RFC9293 Section3.1](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.1)
- [tcpdump4.99.1 manual, offline read and numeric timestamps](https://github.com/the-tcpdump-group/tcpdump/blob/tcpdump-4.99.1/tcpdump.1.in)
- [libpcap1.10.1 savefile description](https://github.com/the-tcpdump-group/libpcap/blob/libpcap-1.10.1/pcap-savefile.manfile.in)

RAG retrieval supplied the general flow-timeout definitions in RFC6645
Sections2.2.3–2.2.4 but no applicable passage for the historical Zeek semantics
or this dataset-specific join. Those points were checked in the primary
sources above. Missing evidence remains a limit, rather than a recovered
historical configuration.
