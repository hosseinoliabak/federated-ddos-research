# Offline fragment and label reconciliation

This extension tests whether the saved UDP fragments can be associated with
complete datagrams and the original source connection labels. It uses the
official pinned TShark CLI to propose membership, then independently checks
the bytes and frame lineage. Frozen version 1 and its completed development
capture audit remain historical evidence. The current review candidate uses
`raw-fragment-policy-v2.json`; its corrected acquired-capture audit has not
run. A tool-produced row alone does not establish a label.

Version 2 vetoes every recognizable standard key touched by a rejected
proposal, including early failures with no materialized record and rejected
mixed-key groups. It explicitly quarantines multiple occurrences of scalar
TShark fields, even when their text values agree. It does not guess the
first protocol instance. Clear singleton field values keep their earlier
interpretation. The original constituent-frame list remains multi-valued.
The Wireshark v4.6.9 TShark manual, field-print options at lines 336–344,
defines occurrence and aggregation; multiple values are not a verified
single protocol context.

Converted packet metadata also retains VLAN tag depth. The depth is a
count, not the tag-stack identity; it does not change connection keys or
establish a tenant/source-label mapping.

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

## Version 2 reference diagnostics

Complete nonfragment IPv4 header, TCP and UDP checksums are counted separately, including affected admitted source rows. This audit does not add a checksum admission veto or infer the historical ignore/offload setting. UDP checksum absence is distinct from a valid checksum. IPv4 checksum zero is checked by its arithmetic result, not treated as an absence marker. The result remains a quarantined counter/label reference, not a claim of protocol-valid wire traffic.

For source rows containing validated UDP datagrams, a separate streaming read compares original orig_bytes/resp_bytes with joined UDP payload bytes. IP total length, UDP payload length and original wire bytes retain separate names. An unset payload counter stays unavailable; a mismatch is visible and does not silently change admission. Zeek v2.6.1 conn.bro lines 32–38/231–236 and UDP.cc lines 105–107/147–177/198–212 support this candidate comparison, without establishing the historical installed build.

The report includes member-time spans within datagrams and original-wire gaps for reconstructed source rows. These are full-trace reference diagnostics. They cannot supply unsampled values to a future sampled feature. Existing complete meter outputs are retained, with distinct token-set categories and source-row/cache-record histograms. A source row or cache record is not an independent episode.

Under the implemented active-first rule, an idle threshold at least as large as the active threshold cannot take the idle branch. Such cells are marked structurally masked. Other cells remain mechanical checks until a source supplies an appropriate contrast. This annotation does not change expiration order or identify an idle effect.
