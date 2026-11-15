# Topology and IP/interface plan v2.1 (PROPOSAL for the owner)

Status: PROPOSAL for the owner’s topology and IP review, revised after review round 2. Nothing is built or started. This v2.1 changes the routing wording only. The convergence gate now requires a unique next hop for each customer /24 at every transit router, and redistribution is excluded in both directions (no BGP-to-OSPF and no OSPF-to-BGP). Every address, interface, autonomous-system number, and table is unchanged from v2. The v1 and v2 files are kept unchanged.

The schematic is in `schematic/`. For v2.1, `build_diagram.v2.1.py` generates `federated-ddos-topology.v2.1.drawio` (editable draw.io) and `federated-ddos-topology.v2.1.svg` (standalone SVG), and `caption.v2.1.txt` is the caption. The v2.1 figure differs from the v2 figure in two text labels only, the subtitle version and the redistribution note.

Provenance of the numbers in this file. FROM-SOURCE (`OWNER-DECISION-OPTION-3-20261115.json`, owner addenda of 2026-11-15): the three RFC 5737 blocks for the outside, the 10.x range for the inside, no network address translation, eBGP at the edge with OSPF inside in FRRouting, two to three upstream transit routers with private autonomous-system numbers, and IPv4 only. FROM-SOURCE (`DESIGN-REVIEW-ROUND1-20261115.md`, owner input during review): static routing everywhere is acceptable as a fallback. PROPOSED (carried from v2 without change): every specific address, interface name, /26 and /31 split, autonomous-system number, and node count. DERIVED: the address totals and the expected next hops, each shown with its basis where it appears.

## Inside and outside boundary

Inside (customers and provider) keeps 10.203.0.0/16, with out-of-band management in 10.204.0.0/24 and collection and services in 10.204.10.0/24. ISP router loopbacks are inside, in 10.203.255.0/24. Outside (the Internet side) uses the three RFC 5737 TEST-NET blocks. No network address translation anywhere; IPv4 only; no IPv6.

## The Observation Point, defined exactly

The OP is forwarded IPv4 traffic toward a customer /24, metered once at that customer’s own border router, on the inbound side; p0 is unsampled and pS applies the 1-in-4 HMAC selector. Return traffic is not metered. Because the OP is defined by “toward a customer /24”, BGP and OSPF control-plane packets, which are not toward a customer /24, are outside every per-customer aggregate by definition. Ingress pinning (below) makes “metered once at its own border router” hold.

## Single ASN table

| Autonomous system | Role | Number |
|---|---|---|
| ISP | BR-1, BR-2 | 64512 |
| Transit A | TR-A, originates 192.0.2.0/24 | 64513 |
| Transit B | TR-B, originates 198.51.100.0/24 | 64514 |
| Transit C | TR-C, originates 203.0.113.0/24 | 64515 |

Private two-byte numbers (RFC 6996, 64512–65534).

## Role, container/namespace, prefix, address, link, meter table

“ns” is a network namespace; “ctr” is a Docker container with FRRouting. OP marks the metered Observation Point.

| Role | Realization | Key interfaces and addresses | Links | Meter |
|---|---|---|---|---|
| TR-A (AS 64513) | ctr (FRR) | to BR-1 203.0.113.225/31, to BR-2 203.0.113.231/31; loopback 192.0.2.193/32; site gateways in 192.0.2.0/26, .64/26, .128/26 | eBGP to BR-1, BR-2 | no |
| TR-B (AS 64514) | ctr (FRR) | to BR-1 203.0.113.227/31, to BR-2 203.0.113.233/31; loopback 198.51.100.193/32; site gateways in 198.51.100.0/26, .64/26, .128/26 | eBGP to BR-1, BR-2 | no |
| TR-C (AS 64515) | ctr (FRR) | to BR-1 203.0.113.229/31, to BR-2 203.0.113.235/31; loopback 203.0.113.193/32; site gateways in 203.0.113.0/26, .64/26, .128/26 | eBGP to BR-1, BR-2 | no |
| Bots (~120) | ns each | one host address each in the /26 host sites of all three blocks | veth to the site bridge | metered at BR-1/BR-2 |
| Benign clients (~120) | ns each | one host address each, interleaved with bots in the same /26 sites (distinct sources ≥ bot count) | veth to the site bridge | metered at BR-1/BR-2 |
| Reflectors (≥24) | ns each | addresses in the TEST-NET host sites; scripted responders | veth to the site bridge | metered at BR-1/BR-2 |
| BR-1 (AS 64512) | ctr (FRR) | up-a 203.0.113.224/31, up-b .226/31, up-c .228/31; data-pe 10.203.0.1/30; core 10.203.0.17/30; mgmt0 10.204.0.11/24; svc0 10.204.10.11/24; loopback 10.203.255.1/32 | eBGP to TR-A/B/C; OSPF to PE-1, BR-2 | **OP**: inbound to 10.203.10.0/24 |
| BR-2 (AS 64512) | ctr (FRR) | up-a 203.0.113.230/31, up-b .232/31, up-c .234/31; data-pe 10.203.0.9/30; core 10.203.0.18/30; mgmt0 10.204.0.31/24; svc0 10.204.10.21/24; loopback 10.203.255.2/32 | eBGP to TR-A/B/C; OSPF to PE-2, BR-1 | **OP**: inbound to 10.203.20.0/24 |
| PE-1 | ctr (FRR) | data-br 10.203.0.2/30; data-ce 10.203.0.5/30; mgmt0 10.204.0.12/24; loopback 10.203.255.3/32 | OSPF to BR-1; link to CE-1 | no |
| PE-2 | ctr (FRR) | data-br 10.203.0.10/30; data-ce 10.203.0.13/30; mgmt0 10.204.0.32/24; loopback 10.203.255.4/32 | OSPF to BR-2; link to CE-2 | no |
| CE-1 | ctr or ns | data-pe 10.203.0.6/30; data-lan 10.203.10.1/24; mgmt0 10.204.0.13/24 | link to PE-1; LAN to CUST-1 | no |
| CE-2 | ctr or ns | data-pe 10.203.0.14/30; data-lan 10.203.20.1/24; mgmt0 10.204.0.33/24 | link to PE-2; LAN to CUST-2 | no |
| CUST-1 (victim 1) | ns | data0 10.203.10.10/24 (TCP listen, UDP sink, HTTP server) | LAN to CE-1 | target |
| CUST-2 (victim 2) | ns | data0 10.203.20.10/24 (same services) | LAN to CE-2 | target |
| POP-1 | ns | mgmt0 10.204.0.14/24; svc0 10.204.10.12/24 | services plane (out of band) | collector + FL client |
| POP-2 | ns | mgmt0 10.204.0.34/24; svc0 10.204.10.22/24 | services plane (out of band) | collector + FL client |
| SVC-1 | ns | mgmt0 10.204.0.20/24; svc0 10.204.10.100/24 (coordinator) + 10.204.10.110/24 (alert rx) | services plane (out of band) | FedAvg / alert |

## Address allocation per TEST-NET block (corrected)

Each /24 gives three /26 host sites and reserves the fourth /26 (`.192/26`) for infrastructure, so no loopback sits inside a host site. Bots and benign clients are interleaved in the same host sites by a frozen assignment.

| Block | AS / transit | /26 host sites | Infra /26 (.192/26) | Bots | Benign | Reflectors |
|---|---|---|---|---|---|---|
| 192.0.2.0/24 | 64513 / TR-A | A1 .0/26, A2 .64/26, A3 .128/26 | loopback .193 | ~40 | ~40 | ~8 |
| 198.51.100.0/24 | 64514 / TR-B | B1 .0/26, B2 .64/26, B3 .128/26 | loopback .193 | ~40 | ~40 | ~8 |
| 203.0.113.0/24 | 64515 / TR-C | C1 .0/26, C2 .64/26, C3 .128/26 | loopback .193 + six transit /31s (.224–.235) | ~40 | ~40 | ~8 |
| Total | | 9 /26 host sites | | ~120 | ~120 | ~24 |

Usable addresses (DERIVED): 762 in the three /24s (3 × 254); about 576 addresses across the nine /26 host sites after the infra reservation (9 × 64, before the network, broadcast, and gateway address of each site are subtracted); about 264 are used (120 + 120 + 24). Real botnets span far more prefixes and addresses; this is an external-validity limit.

## Routing (ingress-pinned eBGP, OSPF, static fallback)

Edge, eBGP, ingress-pinned. BR-1 advertises only 10.203.10.0/24 and BR-2 only 10.203.20.0/24 to all three transit routers, so a victim’s traffic enters at its own metered border router. Each border router originates its one customer /24 into BGP as a single named prefix, and an outbound prefix filter on each of its three eBGP sessions permits that /24 and nothing else.

No redistribution in either direction. BGP routes are not redistributed into OSPF, and OSPF routes, like connected and static routes, are not redistributed into BGP. The second half matters for the pinning. Each border router learns the other customer’s /24 by OSPF, so redistributing OSPF into BGP would make it advertise that /24 as well, and the transit routers would then have a second way in that bypasses the victim’s own meter. The inside reaches TEST-NET by a default route.

Inside, OSPF area 0 across BR-1, BR-2, PE-1, PE-2 (core link 10.203.0.16/30); the provider-edge to customer-edge links carry the customer /24s as connected or static routes.

Convergence and unique-next-hop gate before any traffic: every eBGP session Established, every OSPF neighbour Full, every prefix present, and a per-transit readback showing that each customer /24 has a unique next hop. On each transit router, 10.203.10.0/24 must have exactly one BGP path and exactly one forwarding next hop, which is the BR-1 address on that router’s link to BR-1, and 10.203.20.0/24 must have exactly one path and one next hop, which is the BR-2 address on its link to BR-2. A second path fails the gate even when it is not the best path. An equal-cost pair fails it, and so does a static route for either prefix on a transit router. On each border router, the advertised-routes readback for each of its three sessions must list its own customer /24 and nothing else. A per-router route-table readback is recorded.

Expected next hops (DERIVED from the link addresses in the table above):

| Transit router | 10.203.10.0/24, only via BR-1 | 10.203.20.0/24, only via BR-2 |
|---|---|---|
| TR-A | 203.0.113.224 | 203.0.113.230 |
| TR-B | 203.0.113.226 | 203.0.113.232 |
| TR-C | 203.0.113.228 | 203.0.113.234 |

Control-plane at the meter: BGP (TCP/179) and OSPF (IP protocol 89) are not toward a customer /24, so they are outside every per-customer aggregate by the OP definition; they are captured for the conservation chain and checked not to appear in any customer bin.

FRRouting pinned and audited, installed offline, no download.

Pre-registered fallback: static routing everywhere, chosen before any data if FRRouting cannot be pinned and audited or the convergence or next-hop gate fails. Static routes install the same ingress pinning (each victim /24 reached from the Internet side only via its own border router) and a static default inside; the convergence gate becomes a static route-table readback with the same unique-next-hop checks, that is, one static route and one next hop for each customer /24 on each transit router, as in the table above. The realism cost (no dynamic convergence, no control-plane traffic to tolerate) is stated in the design threats.

## Isolation proof additions for the public-side addresses

No node, including every bot, reflector, and benign client, has a route to any non-lab prefix or a default route out of the virtual machine. A root-namespace guard drops and counts anything leaving the lab bridges. BGP and OSPF (or the static routes) exist only on declared lab links; each router’s table is read back and the unique next hop of each customer /24 checked. An egress probe from a bot namespace to a non-lab address must fail; the positive control (a bot reaching its victim over the metered path) must succeed. IPv6 disabled on every interface and bridge. No network address translation anywhere. The virtual machine denies egress at its own boundary.

## Diff from the approved 7-role layout

The 7-role pilot was {GEN-1, BR-1, PE-1, CE-1, CUST-1, POP-1, SVC-1} on one path with a single source distinguished only by source port. This proposal replaces GEN-1 with ~120 bots, ~120 benign clients, and ≥24 reflectors in several TEST-NET /26 sites; adds three transit autonomous systems running FRRouting with ingress-pinned eBGP; instantiates the second site and point of presence (BR-2, PE-2, CE-2, CUST-2, POP-2) from the 13-role reference so federation has two clients; adds OSPF area 0 inside; and keeps all customer and provider addressing in 10.203.0.0/16 with the services plane out of band. The Observation Point, collector placement, and detection-only rule are unchanged.
