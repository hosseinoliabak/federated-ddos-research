# Offline fragment and label reconciliation

This extension tests whether the saved UDP fragments can be associated with
complete datagrams and the original source connection labels. It uses the
official pinned TShark CLI to propose membership, then independently checks
the bytes and frame lineage against `raw-fragment-policy-v1.json`. The policy
is fixed before the actual development-capture audit. A tool-produced row
alone does not establish a label.

The validator rejects overlaps, holes, malformed/truncated fragments, mixed
keys or VLAN context, checksum/transport disagreements and ambiguous observed
ID reuse. It allows out-of-order arrival when the full membership is
otherwise complete. Sequential reused IDs require strictly separated
constituent time and frame-order windows; any same-key unresolved fragment
vetoes that key. This is a conservative observed-trace rule. It does not
establish the maximum lifetime or ID uniqueness of unobserved Internet
packets.

Validated datagrams retain their original fragments. The two observation
units have different packet and IP-byte totals. For comparison with the
source connection log, datagrams use their completion-arrival timestamps,
then the unchanged base90a exact tuple/time/directional-counter checks.
Historical Zeekv2.6.1 `Sessions.cc` lines369–407,709–766 passes the completing
arrival time into connection processing after reassembly. Its legacy key at
918–941 differs from the RFC source/destination/protocol/ID key, so this
extension is not a replication of an identified original installation.

Reassembly here supplies offline label reference. RFC1812 Section5.2.6
prohibits transit-router reassembly before forwarding; it does not decide
whether separate detector software may examine copies. A detector-copy
fragment cache, its costs and its sampling position would be explicit lab
choices. Sampling wire fragments before reconstruction also differs from
sampling complete datagrams afterward. The diagnostic reports both selection
boundaries without using unsampled bytes to create sampled features. No
live policy or model result follows from this admission.

Primary design references are RFC791 Sections3.1–3.2, RFC815 Sections2–3/7,
RFC6864 Sections3.1/6.1, RFC6274 fragmentation-security discussion,
RFC1071 Section1 and RFC768 UDP format/checksum. RAG supplied relevant
RFC815, RFC1071, RFC1812 and ID/reassembly-risk passages. Historical Zeek
sources and the pinned official Wireshark field/CLI documentation were read
directly. RFC815 describes completeness, while overlap rejection is an
explicit conservative admission choice rather than a claimed universal IPv4
receiver rule.

The private contract names exact originals, code/policy/lock hashes, the
pinned CLI binary and a new output directory inside `FDDOS_WORKSPACE`.
Originals must remain0444. No capture, replay, DNS, installation, benchmark
adoption, final-source inspection or model fitting is performed. No raw
traffic or runtime outputs belong in a public commit.
