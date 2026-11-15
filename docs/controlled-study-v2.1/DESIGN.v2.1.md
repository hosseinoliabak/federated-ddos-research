# Option 3 controlled study: design v2.1

Status: DESIGN ONLY, a narrow revision of v2 after review round 2 (`DESIGN-REVIEW-ROUND2-20261115.md`). This is a proposal for a final check, not a freeze or an execution release. The design worker wrote no generator code, packet bytes, attack-packet fixtures, or schedule files, and the lab virtual machine stayed stopped. The project safety boundary is a hard stop. Every number is DERIVED (with its derivation), FROM-SOURCE (with a locator), or PROPOSED (with a reason). A number without a label in a passage marked as unchanged from v2 keeps the label it has in v2. The word “contributor” is used for the second federated client.

The study keeps the identity it had in v2: a new, separately pre-registered study. The old confirmatory lab track and its requalification-gate failure stay reported unchanged, as recorded. `RESPONSE-TO-REVIEWS-R2.md` maps each round-2 finding to its change. The v1 and v2 files are kept unchanged beside these.

Sibling files: `DESIGN.v2.1.json`, `TOPOLOGY-IP-PROPOSAL.v2.1.md`, `OWNER-DECISIONS-NEEDED.v2.1.md`, `REVIEW-PACKET.v2.1.md`, `RESPONSE-TO-REVIEWS-R2.md`, `PROPOSITIONS-FOR-LEAN.v2.1.md`, the v2.1 figure files in `schematic/`, and `v2.1-computation/`.

**What changed from v2.**

1. The RQ2 predictions are recomputed exactly from the negative-binomial model. The thresholds are 96 (p0) and 104 (pS), not the Gaussian 84 (section I).
2. The ratio levels gain r = 2.5 and r = 4.0, and r = 1.0 stays as a descriptive anchor (sections A2, D-caps).
3. Each ratio is mapped to one claim with a decision rule. H2-sensitive is judged at r = 1.5, 2.0, 2.5, H2-volume by an equivalence rule at r = 4.0 and 5.0, and r = 3.0 is a transition level (section A2).
4. The primary scorer for H2 is the packets ×4 threshold rule. The full-schema MLP is secondary (sections A2, F).
5. Distinct hosts are predicted from the bin total, and the population-guard claim is withdrawn (sections C, I).
6. The episode table is reallocated, the calibration pool is enlarged, the confirming interval is named, block agreement is redefined, qualification has its own row, and the totals are recomputed (section G).
7. RQ1 and RQ4 have fixed roles, an exact TRAIN grid, a FINAL recipient-evaluation mapping, defined contrasts, added FedAvg fits, and a standardization rule under mismatch (sections A3, F).
8. Gates and routing are tightened: the feasibility threshold is frozen, the dry run uses the stated aggregate rate, the ±10% rate tolerance applies to the plateau only, the fallback keeps one-second bins, the convergence gate requires a unique next hop, redistribution is excluded in both directions, and the SVG path is in the JSON (sections D-routing, D-caps, H).
9. Two wordings are corrected: the calibration pool is one per prefix, and the unscaled-mismatch sentence includes r = 5 (sections G, I).

**Where the new numbers come from.** One seeded script, `v2.1-computation/v21_planning_computation.py`, produced every new prediction. It models per-bin packet counts statistically and creates no traffic. Its exact part sums probability mass functions. Its simulated part repeats the planned procedure end to end. The run record `v2.1-computation/RUN-RECORD.json` holds the script hash, the interpreter, the seeds, the draw counts, the UTC times, and the cited outputs. The script first reproduced Root’s five rows (section I).

---

## A1. Research questions, architecture, and the change from the old track

The study keeps the four core research questions and serves three with controlled lab evidence (FROM-SOURCE: `chapters/01-introduction.tex` RQ section, as cited in v2). The placement is the approved one: detection at the router, a separate collector and federated-learning client at each point of presence, a separate coordinator and alert receiver, detection only. Federated learning needs at least two clients, so two customer sites and two points of presence are instantiated. The contributor count is **one** (one contributor plus the recipient, so two clients), stated as in the protocol.

v2.1 names the two roles (PROPOSED). POP-1, with the customer prefix 10.203.10.0/24 metered at BR-1, is the **recipient**. POP-2, with 10.203.20.0/24 metered at BR-2, is the **contributor**. The roles are the same in both acquisition blocks.

Why the study changed: the old attacks were one 60-octet packet per 5-tuple about once per second, a gap longer than the 500 ms idle timeout, so every packet closed as its own one-packet record that looked like a benign opening SYN; the unit of analysis was one record while router-side DDoS detection rests on aggregates; the attack ran at about three packets per second against about two benign transactions per second under a 50 pps cap. The pre-registered gate correctly stopped 168 fits (FROM-SOURCE: `claude-handoff-20261115-v62/HANDOFF.txt` section 2, as cited in v2).

## A2. RQ2 is the heart: the split hypothesis, its scorer, and the ratio-to-claim map

RQ2 asks how 1-in-4 packet sampling changes aggregate detection. H2 stays split into two halves, as in v2. v2.1 fixes three things that v2 left open: the scorer, the ratios at which each half is judged, and the decision rule.

**Primary scorer.** H2 is judged on the **packets ×4 threshold rule**. The score of a one-second bin is the per-prefix packet count, multiplied by 4 under pS, and the bin alerts if its score is strictly greater than a threshold read from benign calibration windows (section G). The rule has no fitted parameter, so the comparison of p0 and pS rests on the metering alone. The full-schema MLP is a secondary scorer.

**Paired drop.** For a set of attack windows, the paired drop is the recall under p0 minus the recall under pS on the same windows, each policy at its own 1% FPR threshold. Its confirming interval is the 95% percentile cluster-bootstrap interval of section G; the 95% level is PROPOSED.

- **H2-sensitive.** At overlap ratios, where the benign and attack-window counts overlap, sampling costs recall, so the paired drop is above zero. It is judged at r ∈ {1.5, 2.0, 2.5}, for the SYN flood and the UDP flood separately, in the many-slow configuration. The primary cell is r = 2.0, the predicted peak. The verdict is **support** if the lower end of the interval is above zero. It is **against** if the interval contains zero and its upper end is at or below 0.05, or if the whole interval lies below zero. It is **inconclusive** otherwise.
- **H2-volume.** At ratios where the unsampled recall is high and the predicted drop is at most 0.05, the rescaled volume count keeps its recall, so the paired drop stays within a margin of 0.05 (PROPOSED in v2, unchanged). It is judged at r ∈ {4.0, 5.0}, with the two flood types and both bot configurations pooled. The primary cell is r = 5.0. The verdict follows the equivalence rule: **support** if the upper end of the interval is at or below 0.05, **against** if the lower end is above 0.05, and **inconclusive** otherwise. Formally this is a one-sided non-inferiority test of pS against p0 with margin 0.05, not a two-sided equivalence test (TOST): the lower end is not bounded, because at r ≥ 4.0 the unsampled recall is close to 1 and a large negative drop cannot occur. (Round 3, Gemini.)

**Ratio-to-claim map.** The predicted values are DERIVED in section I. The levels are PROPOSED.

| r | Attack peak (pps) | Recall p0 | Recall pS | Predicted drop | Claim judged at this ratio |
|---|---|---|---|---|---|
| 1.0 | 40 | 0.189 | 0.148 | 0.041 | None. Low anchor of the curve. The unsampled recall is low, so H2-volume does not apply, and the drop is too small to detect. |
| 1.5 | 60 | 0.523 | 0.378 | 0.145 | H2-sensitive |
| 2.0 | 80 | 0.885 | 0.671 | 0.214 | H2-sensitive, primary cell (predicted peak) |
| 2.5 | 100 | 0.994 | 0.883 | 0.111 | H2-sensitive |
| 3.0 | 120 | 1.000 | 0.972 | 0.028 | Transition level. The predicted drop is inside the margin, so the H2-volume rule is applied, but as a secondary cell that is expected to return inconclusive more often than support (section G). |
| 4.0 | 160 | 1.000 | 0.999 | 0.001 | H2-volume |
| 5.0 | 200 | 1.000 | 1.000 | 0.000 | H2-volume, primary cell |

v2 had five levels. r = 2.5 is added because the exact curve still predicts a drop of 0.111 there. r = 4.0 is added because it gives H2-volume a second ratio whose predicted drop is far from the margin. r = 1.0 is kept as the low end of the curve, where the drop is small because both recalls are small. The maximum attack peak is unchanged at 200 pps.

The other parts of H2-sensitive are secondary. For distinct source hosts the design no longer predicts a drop of a given sign (section I), so the paired change is reported as a two-sided estimate for each bot configuration. For the per-record arm the drop is predicted by the collision ceiling (section M).

**The intensity-ratio sweep (the RQ2 deliverable).** The attack-to-benign intensity ratio r is the ratio of attack packets to benign packets reaching a victim prefix in a one-second window. The deliverable is a **curve per feature family**: the ratio at which 1-in-4 sampling starts to cost recall and the ratio at which it stops, for the volume family, the structural family, and the per-record arm, and the contrast between the many-slow and few-fast bot configurations at fixed total volume.

## A3. RQ1 and RQ4: roles, the TRAIN grid, the evaluation mapping, and the contrasts

RQ1 (controlled federated versus local versus pooled versus statistical collaboration) and RQ4 (policy mismatch and complementary evidence) rest on an attack-type matrix across the two points of presence, as in v2. v2.1 pins the matrix, the episodes behind it, and the contrasts. One feature schema is used for all methods.

**Roles of the attack types (PROPOSED).**

| Attack type | Role | In the recipient’s TRAIN | In the contributor’s TRAIN |
|---|---|---|---|
| SYN flood | contributor-only; the recipient’s focal type | no | yes |
| UDP flood | shared | yes | yes |
| HTTP flood | shared | yes | yes |
| Reflection | recipient-only | yes | no |

The SYN flood is the focal type because its signature differs most from what the recipient sees in its own TRAIN. The recipient’s own floods raise the UDP share or the bytes per packet, while a SYN flood raises the SYN count and lowers the bytes per packet. The contributor’s evidence is then complementary in feature space and not only in name. All four types raise the packet count, however, so a recipient that leans on the count alone may already detect the focal type. A gain of zero is a pre-registered possible result.

**Exact TRAIN grid per block (PROPOSED).** Every attack TRAIN cell has two many-slow episodes, one at r = 2.0 and one at r = 5.0, aimed at the prefix of the point of presence that trains on them. Reflection has no bot configuration and uses the same two ratios.

| TRAIN cell | Target prefix | Episodes per block |
|---|---|---|
| SYN, contributor | CUST-2 | 2 |
| UDP, recipient | CUST-1 | 2 |
| UDP, contributor | CUST-2 | 2 |
| HTTP, recipient | CUST-1 | 2 |
| HTTP, contributor | CUST-2 | 2 |
| Reflection, recipient | CUST-1 | 2 |
| UDP substitute, contributor (used only in the evidence-absent fits, in place of the two SYN episodes) | CUST-2 | 2 |
| Benign-only (benign TRAIN rows for both points of presence) | none | 4 |
| **TRAIN per block** | | **18** |

Each attack TRAIN episode gives 60 plateau windows labelled attack at its target prefix, and ramp windows are not used for training. Each benign-only episode gives 100 benign windows at each prefix. A point of presence therefore trains on 360 attack windows and 400 benign windows per block (DERIVED: 3 cells × 2 episodes × 60, and 4 × 100). The contributor has the same 360 attack windows with the SYN episodes or with the substitute episodes.

**FINAL recipient-evaluation mapping.** All FINAL attack episodes target the recipient’s prefix (CUST-1, metered at BR-1). The same FINAL episodes therefore serve RQ2 and the recipient evaluation of RQ1 and RQ4.

| FINAL family at the recipient prefix | Episodes over both blocks | RQ2 use | RQ1 and RQ4 use |
|---|---|---|---|
| SYN, many-slow, r = 1.5, 2.0, 2.5 | 12 at each ratio | H2-sensitive cells | focal type: the RQ1 primary gain and the RQ4 contrasts |
| UDP, many-slow, r = 1.5, 2.0, 2.5 | 12 at each ratio | H2-sensitive cells | shared type: control, no gain expected |
| SYN and UDP at r = 1.0, 3.0, 4.0, 5.0, one episode per configuration per block | 4 per type at each ratio | ends of the curve; H2-volume cells at r = 4.0 and 5.0 | descriptive |
| SYN and UDP, few-fast, r = 2.0 | 4 per type | configuration contrast, secondary | descriptive |
| Reflection, r = 2.0 and 5.0 | 4 at each ratio | volume-only, descriptive | recipient-only type: check that federation does not lower recall |
| HTTP, two configurations, r = 2.0 and 5.0 | 4 per configuration at each ratio | descriptive; an honest negative is pre-registered | shared type, descriptive |

The recipient’s recall for RQ1 and RQ4 is computed at p0 on the plateau windows of the many-slow FINAL episodes of one type, pooled over the three overlap ratios with equal weight (36 episodes for SYN and 36 for UDP). Each model reads its threshold from the recipient’s calibration pool. RQ1 compares FedAvg, Pooled, Local-recipient, and the AF arm on the focal type, and its primary contrast is FedAvg minus Local-recipient.

**RQ4 cells and contrasts.** RQ4 uses four FedAvg cells. In all four the recipient meters at p0, there is one contributor, and the contributor’s TRAIN has the same volume. The contributor meters either at p0 or at pS, where pS re-meters the same captured packets. Its TRAIN holds either the two SYN episodes (complementary evidence) or the two substitute UDP episodes (no complementary evidence). Write R for the recipient’s recall on the focal type.

Write Y_ce for R in the cell with contributor policy c (0 = p0, 1 = pS) and evidence e (0 = substitute episodes, 1 = SYN episodes). The contrasts follow the RQ4 protocol (PROTOCOL.md, line 114) exactly:

- **D_C** (policy mismatch) = ((Y_10 − Y_00) + (Y_11 − Y_01)) / 2, the mismatch effect averaged over both evidence levels.
- **D_E** (complementary evidence) = ((Y_01 − Y_00) + (Y_11 − Y_10)) / 2, the evidence effect averaged over both policies.
- **D_CE** (interaction) = (Y_11 − Y_10) − (Y_01 − Y_00), which tells how much of the evidence gain survives the mismatch.

All four values Y_00, Y_01, Y_10, Y_11 are reported beside the contrasts, so the simple effects can be read directly. D_C and D_CE are each reported twice, once for the unscaled and once for the rescaled contributor (section F). The contributor count and the pre-policy volume are fixed in every cell, as v2 required. If a required cell is unavailable, the contrast is reported as unavailable with its reason. (Root amendment, 2026-11-15: the worker’s draft used simple effects for D_C and D_E and the joint effect Y_11 − Y_00 for D_CE; its “interaction” equalled the protocol’s D_CE. The original is kept in DESIGN.v2.1.worker-original.md.)

**Policy and rescale arms for single models** are unchanged from v2: train p0 / test p0 (baseline); train p0 / test pS **without rescaling** (the Kopmann scale shift, predicted to collapse recall); train p0 / test pS **rescaled ×4** (predicted to recover the volume signal, not the structural signal); train pS / test pS (same rate, intermediate).

---

## B. Topology, addressing, and the Observation Point

Unchanged from v2. Inside keeps 10.203.0.0/16 (customers and provider), management 10.204.0.0/24, collection and services 10.204.10.0/24. The services and collection plane is **out of band** from the data plane. Outside uses the three RFC 5737 TEST-NET blocks for bots, reflectors, external benign clients, and transit links. No network address translation anywhere; IPv4 only. The outside blocks, the inside range, the absence of NAT, and IPv4 only are FROM-SOURCE (`OWNER-DECISION-OPTION-3-20261115.json`, owner addenda). Every specific address is PROPOSED. Full tables are in `TOPOLOGY-IP-PROPOSAL.v2.1.md`, and the figure is `schematic/federated-ddos-topology.v2.1.svg`.

**The Observation Point, defined exactly.** The OP is **forwarded IPv4 traffic toward a customer /24, metered once at that customer’s own border router** on the inbound (Internet-facing) side, before any sampling in the p0 view and with the 1-in-4 HMAC selector in the pS view. “Metered once” means a packet is counted at exactly one border router, its ingress, not again elsewhere. Return traffic (victim to source) is not metered, because the aggregate is customer-bound. Each TEST-NET site has a gateway (its transit router) and inbound routes; return routes exist for connectivity but carry no metered traffic. Because the OP is defined by “toward a customer /24”, BGP and OSPF control-plane packets, which are not toward a customer /24, are **outside every per-customer aggregate by definition** (section D-routing).

Ingress is pinned so that a victim’s traffic enters at its own border router (section D-routing), which makes “metered once at its own border router” hold.

---

## C. Traffic design

The botnet is emulated: a small sender per network namespace, each with its own assigned (not spoofed) TEST-NET address, heterogeneous rates, staggered start times, and jitter. No malware, no command-and-control, no real bot code. One kernel and one clock, so a controlled emulation of botnet traffic, not a botnet. Routers run FRRouting in containers; bots, benign clients, and reflectors are network namespaces (lighter than containers; hundreds are feasible).

**Bot population and the scale-versus-rate contrast.** About 120 bots across the TEST-NET /26 host sites (PROPOSED). Two configurations deliver the same peak rate to a victim prefix: many-slow (about 120 bots) and few-fast (about 24 bots). Per-bot rates are heterogeneous, calibrated later from IoT-23 Mirai summary statistics (section K). The peak is set by the ratio sweep (sections A2, D-caps), not fixed at one value.

**Episode targets (PROPOSED).** An attack episode directs its attack at exactly one customer prefix, its target prefix, while benign traffic runs to both prefixes. The other prefix then carries benign-only windows under the same episode role.

**Frozen per-type packet shape, so protocol and port do not separate the classes.** Unchanged from v2, where the responder counts are PROPOSED. Each attack type has a frozen packet size and port distribution, and benign of the **same protocol on the same destination ports** runs concurrently, so a classifier cannot separate on protocol, port, or size alone; it must use volume or structure. In particular:

1. **SYN flood.** Bots open half-open TCP connections to a victim listening service. The SYN packets carry a **realistic kernel-like TCP option set** (maximum segment size, selective-acknowledgement permitted, timestamps, window scale), so the option set is not a fingerprint. Each bot uses many ephemeral source ports to one victim service port, so most connections are short records (per-record arm, section E). The robust aggregate feature is the per-destination SYN count ×4.
2. **UDP flood.** Bots send a UDP datagram stream to a victim sink on a fixed service port; benign UDP runs on the same port. Robust feature: per-destination packet and byte counts ×4.
3. **HTTP application-layer flood.** Bots complete real kernel TCP handshakes and issue HTTP requests to an in-lab HTTP server behind the victim. The contrast is a **same-rate legitimate HTTP crowd**: concurrent benign HTTP at the same request rate from a comparable number of sources. Flow features are expected to fail to separate the two; an honest negative is pre-registered as an informative result. Candidate signal: per-destination request or connection rate.
4. **Reflection and amplification.** Bots send small requests to **at least 24 in-lab scripted responders** (their own TEST-NET addresses, not spoofed) with a **frozen protocol, response size, and amplification gain**; the responders direct the amplified responses to the victim. The victim-side router sees many responder sources with byte amplification. Because six responders would collapse the source count, at least 24 are used; otherwise the reflection type is scoped to **volume-only** features. Construct limit: real reflection uses spoofing; this reproduces the victim-side observable, not the spoofing mechanism.

**Benign model and the validity guard.** Benign is synthetic kernel TCP, UDP, and HTTP from many TEST-NET addresses interleaved with bots in the same /26 sites, calibrated from a natural capture. Benign comes from at least as many source addresses as there are bots (about 120), and the interleave is a **frozen address assignment**, not a random draw, checked at qualification. This parity removes separation by address pool: neither the set of source addresses nor their site tells the classes apart.

The parity does not equalize the number of distinct sources seen in a one-second bin. v2 claimed that it did, and v2.1 withdraws the claim. An attack window adds the active bots to the benign sources of the same bin (section I), and that excess is attack evidence, not an artefact. Per-bin occupancy is close in one place only, the benign flash crowd. A crowd of 240 pps from the 120 benign sources shows about 104 distinct hosts per bin, against 131 in a many-slow attack window at r = 5.0 (DERIVED, section I). The flash crowd therefore tests the distinct-host feature as well as the volume feature.

A **benign flash crowd at the attack peak rate** (benign-only episodes that surge to the attack rate) gives held-out FPR at high benign volume. Benign runs concurrently inside **every** episode, to both customer prefixes, at about 40 pps each.

**Ordered packet label rule.** Unchanged from v2. A packet is labelled by identity, in this precedence: (1) attack if its source is in the bot or responder set and its destination is a victim host, plus the per-type marker; (2) benign if its destination is a benign service identity; (3) control-plane if source and destination are router loopbacks or transit-link endpoints with the routing protocol’s transport; (4) otherwise unmatched and counted. No time-join is needed. Concurrent benign stays inside the attack episode.

**Window labels.** A window is labelled from the unsampled packets. It is an attack window if it lies in the attack plateau of its episode at the target prefix. The label and the episode role are the same under p0 and pS, so both policies are scored on the same windows.

---

## D-routing. Routing (ingress-pinned eBGP, OSPF, static fallback)

FRRouting runs in the router containers; the version is pinned and audited, installed offline, no download during the study. IPv6 is disabled; IPv4 only.

**eBGP, ingress-pinned.** Three transit autonomous systems (64513, 64514, 64515) each originate one TEST-NET /24. The two ISP border routers (64512) run eBGP to all three. The numbers and prefixes are PROPOSED in `TOPOLOGY-IP-PROPOSAL.v2.1.md`. The policy is minimal and deterministic: **each border router advertises only its own customer /24** (BR-1 advertises 10.203.10.0/24, BR-2 advertises 10.203.20.0/24), so traffic for a victim enters at that victim’s own border router and is metered once there. Each border router originates its one customer /24 into BGP as a single named prefix, and an outbound prefix filter on each of its three eBGP sessions permits that /24 and nothing else.

**No redistribution in either direction.** There is no BGP-to-OSPF redistribution and no OSPF-to-BGP redistribution, and connected and static routes are not redistributed into BGP either. The second direction is new wording in v2.1, and it protects the pinning. Each border router learns the other customer’s /24 by OSPF, so redistributing OSPF into BGP would make it advertise that /24 too, and the transit routers would then have a second way in that bypasses the victim’s own meter. The inside reaches the TEST-NET blocks by a **default route**. OSPF runs in a single area 0 across the border routers and provider edges; the provider-edge to customer-edge links carry the customer /24s as connected or static routes. A single area is a small-lab simplification (section J).

**Control-plane packets.** They are not toward a customer /24, so they are outside every per-customer aggregate by the OP definition. They are still captured for the conservation chain and checked not to appear in any customer bin.

**Timers (PROPOSED defaults, not tuned).** BGP keepalive 10 s, hold 30 s; OSPF hello 10 s, dead 40 s.

**Convergence and unique-next-hop gate before any traffic.** Every eBGP session Established, every OSPF neighbour Full, every TEST-NET prefix in each ISP router’s table, every victim /24 in each transit router’s table, and a **per-transit readback of a unique next hop**. On each transit router, 10.203.10.0/24 has exactly one BGP path and exactly one forwarding next hop, which is the BR-1 address on that router’s link to BR-1, and 10.203.20.0/24 has exactly one path and one next hop, which is the BR-2 address on its link to BR-2. A second path fails the gate even when it is not the best path. An equal-cost pair fails it, and so does a static route for either prefix on a transit router. On each border router, the advertised-routes readback of each of its three sessions lists its own customer /24 and nothing else. The six expected next hops are tabulated in `TOPOLOGY-IP-PROPOSAL.v2.1.md`. A per-router route-table readback is recorded.

**Pre-registered fallback: static routing everywhere.** If FRRouting cannot be pinned and audited, or the convergence or next-hop gate fails, the study switches, **before any data**, to static routing everywhere (FROM-SOURCE for its acceptability: owner input recorded in `DESIGN-REVIEW-ROUND1-20261115.md`). Static routes install the same ingress pinning (each victim /24 reached from the Internet side only via its own border router), inside reaches TEST-NET by static default, and the convergence gate is replaced by a static route-table readback with the same unique-next-hop checks. What changes: less routing realism (no dynamic convergence, no control-plane traffic to tolerate), which is stated in the threats (section J). The choice is recorded.

---

## D-caps. Safety and caps

The old caps (300 attack packets, 1,200 benign, 50 pps, 60 s) cannot produce a flood (FROM-SOURCE: v2). The rate caps of v2 are kept. v2.1 changes the ratio levels, the totals, and the fallback.

**Rates (DERIVED).** Benign to a victim prefix is about 40 pps (mean per one-second window μ_B = 40 packets; FROM-SOURCE: v2). The sweep covers r ∈ {1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0}, so the attack peak per victim prefix is A = r·μ_B ∈ {40, 60, 80, 100, 120, 160, 200} pps. The maximum peak stays at **about 200 pps**.

**Peak aggregate rate (DERIVED).** With one target prefix per attack episode, the peak aggregate rate toward the customer prefixes is **280 pps**: 200 attack plus 40 benign at the target prefix, which is 240 pps at the target Observation Point, and 40 benign at the other prefix. A flash-crowd episode reaches the same 280 pps. Reflection episodes add at most 200 pps of bot-to-responder requests outside the customer prefixes, for a packet gain of at least 1, and return traffic from the victims is additional. Neither is metered.

**Proposed hard caps (PROPOSED; values above the old 50 pps / 300-packet caps are OWNER DECISIONS).**

| Cap | Value | Basis |
|---|---|---|
| Per-bot rate | ≤ 20 pps | bounds a few-fast bot (200 pps / 24 ≈ 8.3 on average) |
| Total attack rate, peak aggregate to a victim | ≤ 400 pps | headroom above 200 pps |
| Aggregate kill switch | halt if the measured aggregate exceeds the cap in any 1 s bin | caps bookkeeping |
| Study-wide packet ceiling | ≤ 4.0 million offered packets | the plan is about 3.46 million toward the customer prefixes and at most 3.74 million with every allowance (section G); v2’s 2.5 million rested on an undercount |
| Attack packets per episode | ≤ 24,000; planned maximum 16,000 | an episode at ratio r offers 3,200 × r attack packets (section G) |
| Episode duration | ≤ 120 s; planned 100 s (20 s ramp-up, 60 s plateau, 20 s ramp-down) | onset and decay windows (section G) |
| Benign peak (flash crowd) | ≤ 240 pps | equal to the attack-window total at r = 5.0 |
| Capture snaplen | 1514 at the OP tap, 256 elsewhere | the meter needs the whole IPv4 packet |

**Safety-boundary fallback.** If even the 200 pps peak reaches the project safety boundary, that is a hard stop reported to the owner. The fallback is then a lower peak, 160 pps and then 120 pps (PROPOSED in v2), **with the one-second bins kept**. v2 lengthened the window to keep P ≥ 300. Review round 2 asked to keep the bins, because a longer bin changes the feature and the benign count model. At 160 pps the top ratio is 4.0 and every claim stays testable, with r = 4.0 as the primary H2-volume cell. At 120 pps the top ratio is 3.0, where the equivalence rule is expected to stay inconclusive (section G), so H2-volume is reported as not testable at that peak. Both consequences are pre-registered.

**Isolation proof** (unchanged from v2, with the unique-next-hop check): no default route out of the virtual machine; no route to any non-lab prefix from any node including every TEST-NET source; a root-namespace guard drops and counts anything leaving the lab bridges; BGP and OSPF only on declared lab links with per-router route-table readback; a failing egress probe from a bot namespace and a succeeding positive control; IPv6 disabled; no NAT; virtual-machine egress denied. Routing convergence and the unique-next-hop gate run before any traffic.

**Virtual-machine size (PROPOSED; owner approves):** 6 virtual CPUs, 12 GiB memory, about 40 GiB disk. The peak-load dry run (section H) checks that the virtual machine does not drop or re-order at the stated aggregate rate before any study data.

---

## E. Features (post-selection packet stream; record contrasts from the flow cache)

Unchanged from v2, apart from the note on the primary scorer. The unit of analysis is aggregate, per destination host and per destination /24 prefix, in **epoch-aligned one-second bins** (bin k = floor(timestamp_ms / 1000)). Two feature groups come from two sources, kept separate because IPFIX records straddle one-second bins under the 1,000 ms active timeout (FROM-SOURCE: v2, the metering configuration, with the 500 ms idle timeout).

**Packet-stream features, from the selected packets binned into aligned 1 s bins** (p0 uses all packets; pS uses the selected packets, then rescales by 4):

| Feature | Robust under pS | Note |
|---|---|---|
| packets ×4 | yes | binned selected-packet count ×4; unbiased (P1). As a threshold rule on the per-prefix count it is the primary H2 scorer. |
| bytes ×4 | yes | binned selected IP-octet sum ×4; unbiased (P1) |
| SYN ×4 | yes | count of **sampled SYN packets** (flag on the packet) ×4; unbiased |
| distinct source hosts | no | primary non-robust structural feature; a host with k packets in the bin is missed with probability (3/4)^k, not fixed by ×4 (P6) |
| source-host entropy | shape only | keeps shape, not invertible |
| distinct source /26 | no | coarse structural secondary |
| UDP share, mean bytes per packet | partial | ratios of rescaled counts |

**Record-based contrasts, from the flow cache only** (deliberately non-robust):

| Feature | Note |
|---|---|
| record count | from the flow cache; biased by deletion and collision, not fixed by ×4 |
| mean packets per record | collapses toward 1 under sampling (Duffield 2002 Table I, as cited in v2) |
| single-packet-record share | the collision quantity |

**The per-record baseline arm** scores the existing frozen 14-feature per-record template W (FROM-SOURCE: `w_features.py`, as cited in v2), to show per-record detection degrades under pS while the aggregate arm survives. Its generator shape is specified in section C. The per-record arm has its **own p0 feasibility stop** (section H).

**One feature schema** is used across all methods and both policies; the mismatch arms differ only in train/test policy and rescaling, not in schema. At the top of the sweep (200 pps) a one-second bin holds about 200 attack packets, so the rescaled attack count has a relative standard error of about 12% (DERIVED: √(3/200), P2). At lower ratios the count is smaller and the error larger, which is part of the measured effect, not a defect.

---

## F. Models, standardization, and the fit ceiling

Learners: logistic regression and a small multilayer perceptron (one hidden layer of eight tanh units) on the aggregate schema; a zero-fit threshold rule on packets ×4, which is the **primary scorer for H2**; the AF/BKM statistical arm if its sealed reader admits the data, else reported unavailable. Seeds {0, 1, 2}; FedAvg 20 rounds, full two-client participation, no early stopping; no tuning on evaluation data (all PROPOSED in v2, unchanged).

**Standardization.** Moments come from allowed benign TRAIN rows only, which are the benign-only TRAIN episodes of section A3. Local methods use their own benign moments. FedAvg and Pooled fits in which both clients meter at the same policy use the union benign moments of the two clients, as in v2. Under mismatch (recipient at p0, contributor at pS) the rule depends on the arm.

- **Rescaled contributor.** The contributor multiplies its packet-stream counts (packets, bytes, SYN) by 4 before any moment is computed. The union benign moments are then formed on a common scale.
- **Unscaled contributor.** The contributor’s features stay as metered, and each client standardizes with its **own local benign moments**. No union moments are formed across the two scales. At inference the recipient uses its own moments.

A standardized value does not change when a feature is multiplied by a positive constant (P12). In the unscaled arm the count features therefore reach the model on the same standardized scale as rescaled counts would with local moments, and the federated unscaled arm is not predicted to collapse (DERIVED from P12). What the mismatch still changes in both arms is the thinning variance of the counts (rescaled benign variance 480 against 360, section I) and the features that cannot be rescaled, which are distinct hosts and the record contrasts. The collapse predicted in v2 belongs to the single-model arm (b) below, where one detector and its frozen threshold meet counts at a quarter of their scale.

Policy and rescale arms for single models: (a) train p0 / test p0; (b) train p0 / test pS unscaled; (c) train p0 / test pS rescaled ×4; (d) train pS / test pS. Arms (b) and (c) **reuse the arm-(a) model** (no new fit, re-scoring only). Arm (d) needs a pS-trained model.

**Fit-ceiling arithmetic (DERIVED).**

- Matched fits on the aggregate schema: methods {Local-recipient, Local-contributor, Pooled, FedAvg} (4) × learners {LR, MLP} (2) × seeds (3) × blocks (2) × training policy {p0, pS} (2) = **96 fits**, as in v2.
- Per-record baseline (a reduced grid): methods {Local-recipient, Pooled, FedAvg} (3) × MLP (1) × seeds (3) × blocks (2) × training policy {p0, pS} (2) = **36 fits**, as in v2.
- RQ4 FedAvg cells with the recipient at p0. The cell “contributor at p0 with the SYN episodes” is the matched p0 FedAvg fit already counted. Five more fit families are needed: contributor at p0 with the substitute episodes; contributor at pS, unscaled and rescaled, with the SYN episodes (the hybrid fits that review round 2 found missing); and contributor at pS, unscaled and rescaled, with the substitute episodes. Families (5) × learners (2) × seeds (3) × blocks (2) = **60 fits**.
- Total supervised fits ceiling = 96 + 36 + 60 = **192** (v2: 132). AF builds ≤ **12**. The threshold rule and the re-scoring arms (b, c) are zero-fit.

Wall time for 192 small fits on the host stays on the order of a few host-hours (PROPOSED estimate, as in v2), excluding acquisition and analysis; acquisition is the larger item (section G).

---

## G. Episodes, roles, calibration, and sample size (the episode is the replication unit)

The **episode** is the replication unit; windows within an episode are dependent. Roles (TRAIN, CAL benign-only, DEV, FINAL, and QUALIFICATION) are assigned by **whole episodes**; an episode’s windows carry the same role under both policies and at both prefixes. Contamination guards: no window mixes roles; no recipient FINAL episode entered contributor training; CAL and the flash crowd are episode- and time-disjoint from TRAIN and FINAL; qualification episodes are never reused in another role. Two prospectively reset acquisition blocks allow a repeatability claim.

**Episode structure (PROPOSED).** An episode is 100 s of offered traffic. The attack, or the crowd surge, has a 20 s ramp-up, a 60 s plateau, and a 20 s ramp-down, and benign runs throughout. An attack episode gives 60 plateau windows at its target prefix, which are the primary windows, and 40 ramp windows for the secondary onset and decay analysis. A benign-only episode gives 100 benign windows at each prefix.

**Episode table (PROPOSED; exact counts hashed at freeze).**

| Purpose | Composition per block | Per block | Study |
|---|---|---|---|
| FINAL sweep, SYN | many-slow: 6 each at r = 1.5, 2.0, 2.5 and 1 each at r = 1.0, 3.0, 4.0, 5.0; few-fast: 2 at r = 2.0 and 1 each at r = 1.0, 3.0, 4.0, 5.0 | 28 | 56 |
| FINAL sweep, UDP | the same | 28 | 56 |
| FINAL, HTTP flood | 2 configurations × 2 ratios {2.0, 5.0} × 2 episodes | 8 | 16 |
| FINAL, reflection (volume-only) | 2 ratios {2.0, 5.0} × 2 episodes | 4 | 8 |
| TRAIN attack | the exact grid of section A3 | 14 | 28 |
| TRAIN benign-only | benign TRAIN rows for both points of presence | 4 | 8 |
| CAL benign-only | one calibration pool per prefix: 12 × 100 = 1,200 windows | 12 | 24 |
| Flash crowd, benign-only at the attack peak (held-out FPR) | 2 configurations × 2 episodes | 4 | 8 |
| DEV (engineering checks only) | | 4 | 8 |
| **Two blocks** | | **106** | **212** |
| QUALIFICATION, run once before block 1 and disjoint from every other role | 4 benign-only; 6 attack at r = 3.0 (SYN 2, UDP 2, reflection 2); 3 peak-load dry runs (section H) | | 13 |
| **Study** | | | **225** |

All FINAL attack episodes target the recipient’s prefix (section A3). The confirmatory cells are these.

| Cell | FINAL episodes per block | Pooled over two blocks |
|---|---|---|
| H2-sensitive: one flood type (SYN or UDP), many-slow, one ratio in {1.5, 2.0, 2.5} | 6 | 12 |
| H2-volume: one ratio in {4.0, 5.0}, both flood types and both configurations pooled | 4 | 8 |
| Transition, r = 3.0, pooled the same way (secondary) | 4 | 8 |

Secondary cells follow the same pooling. The anchor at r = 1.0 pools the two flood types and both configurations, the few-fast cell at r = 2.0 pools the two flood types, and each HTTP cell pools the two configurations at one ratio. Each of these has 4 episodes per block. The reflection cells have 2 episodes per block and are reported as point estimates.

**Derived acquisition totals (DERIVED from the table).** An attack episode at ratio r offers 3,200 × r attack packets: 60 s × 40r on the plateau, plus two 20 s linear ramps at half that rate. Every episode offers 8,000 benign packets, which is 40 pps to each of two prefixes for 100 s. A flash-crowd episode adds 16,000 crowd packets.

| Quantity | Value |
|---|---|
| Attack packets toward the customer prefixes | 1,516,800 (FINAL sweeps 844,800; HTTP 179,200; reflection 89,600; TRAIN 313,600; qualification 89,600) |
| Benign packets | 1,944,000 (225 × 8,000, plus 9 flash-crowd surges of 16,000) |
| Total offered toward the customer prefixes | 3,460,800, about **3.46 million** |
| Allowance if every DEV episode ran at r = 5.0 | + 128,000, giving at most 3.59 million |
| Reflection request packets outside the customer prefixes, for a packet gain of at least 1 | at most 153,600, giving at most 3.74 million in all |
| Offered-traffic time, at about 120 s per episode with gaps | 225 × 120 s = **7.5 hours**, over several attended sessions |
| Peak aggregate rate toward the customer prefixes | **280 pps** (section D-caps) |

The v2 figures were about 156 episodes, 1.4 to 1.6 million packets, and 5.2 hours. The v2 packet figure counted benign traffic to one prefix, while benign runs to both. Double-metering (p0 and pS offline) and analysis are additional.

**Calibration pool: one per prefix per block.** The 12 benign-only CAL episodes of a block give 12 × 100 = 1,200 benign windows at each prefix (DERIVED). This is one calibration pool per prefix per block. v2’s phrase “at least 300 benign scores per cell” is withdrawn, because there is no pool per cell. The same pool serves every type, ratio, and configuration evaluated at that prefix in that block, and 300 windows is the floor below which no threshold is computed (FROM-SOURCE: v2). Each scorer reads its threshold from its own scores on the pool windows. The threshold is the ⌈0.99 n⌉-th smallest score, which for n = 1,200 is the 13th largest (DERIVED, P7), and a window alerts only if its score is strictly greater. This is the **tie rule** of v2, unchanged.

**Confirming interval (named method).** The confirming interval is the 95% percentile interval of a cluster bootstrap over whole episodes. Within each block, the 12 calibration episodes are resampled with replacement, and separately the FINAL episodes of the cell. Both thresholds, for p0 and for pS, are recomputed from the resampled calibration windows by the rank rule, and the paired drop of each resampled FINAL episode is recomputed against them. The block value is the mean over the block’s resampled episodes, and the study value is the mean of the two block values. The interval runs from the 2.5th to the 97.5th percentile of 10,000 replicates (PROPOSED), with the seed recorded. An interval is computed only for a cell with at least 4 FINAL episodes per block (PROPOSED), which answers the round-2 finding that a bootstrap on 2 episodes is degenerate. Smaller cells are reported as point estimates per episode. Window-level Clopper–Pearson intervals stay descriptive only.

**Why this method, and not one of the three named in the brief.** Review round 2 raised the dependence of windows inside an episode. The computation shows a second and larger source of error, the calibration threshold. A 1% FPR threshold is an extreme order statistic of the benign pool, and its noise moves the recall of every FINAL window of the block together. With the v2 pool of 360 windows, the p0 threshold has a standard deviation of about 9 counts around 96, and one block’s estimate of the drop at r = 2.0 has a standard deviation of about 0.10, against about 0.04 from FINAL sampling alone (DERIVED, simulation). An interval built from FINAL episodes alone leaves this out.

The script checks each method in a null scenario where the true drop is zero by construction: both policies are independent 1-in-4 selections of the same packets. A t interval on FINAL episode means excludes zero in 17% to 32% of simulated studies with the v2.1 pool, and in 40% to 47% with the v2 pool. BCa with a cluster-jackknife acceleration, over the same resampling as the adopted method, excludes zero in 12% to 21%. The percentile interval that also resamples the calibration episodes excludes zero in 0.9% to 2.8%, below its nominal 5% (all DERIVED, simulation). v2.1 therefore adopts the percentile cluster bootstrap over calibration and FINAL episodes. The studentized bootstrap was not evaluated. It needs a variance estimate inside each replicate that includes the calibration step, and the percentile interval already holds its size.

**Planning values (PROPOSED) and what they imply.** The planning value for the correlation between the paired differences of two windows of one episode is ρ = 0.05. With m = 60 plateau windows the design effect is 1 + 59 × 0.05 = 3.95 (DERIVED, P9). Its basis is the design effect of about 4 named in review round 2 (FROM-SOURCE: `DESIGN-REVIEW-ROUND2-20261115.md`). The lab has produced no data, so no measured value exists. The exact model shows that the value is conservative. Pairing removes most of the shared benign variation, and a design effect of 3.2 to 5.0 for the paired difference needs about 80% of the benign rate variance to sit between episodes. With 20% between episodes the design effect is 1.36 to 1.87 at the three overlap ratios (DERIVED). At 80% it is 4.20, 3.19 and 4.95 at r = 1.5, 2.0 and 2.5 (ICC 0.054, 0.037, 0.067; DERIVED, Root recomputation with the script’s icc_paired_difference), so ρ = 0.05 is slightly conservative at the primary ratio and slightly low at r = 2.5 and r = 1.5. The episode counts do not change, because the simulated verdict probabilities use the generating model, not ρ. (Round 3, Grok; values checked by Root.) The simulation uses these two settings, called the strong and the moderate episode effect, and a third with independent windows.

The simulation repeats the planned procedure. Each simulated study has two blocks. In each block the script draws the calibration pool, sets both thresholds by the rank rule, draws the FINAL episodes of each cell, and computes the interval with 500 bootstrap replicates. Every window keeps the negative-binomial margin of the benign count, and a share of the benign rate that is common to the windows of one episode (80%, 20%, or none) makes those windows dependent (P10). The master seed is 20261115, and each configuration has 2,000 or 4,000 simulated studies (`v2.1-computation/RUN-RECORD.json`).

The FINAL sampling part follows directly from the planning values. At the predicted peak, r = 2.0, the per-window variance of the paired difference is 0.2071 (DERIVED, P8), so one episode’s drop has a standard deviation of √(0.2071 × 3.95 / 60) = 0.117. Four episodes, the v2 count, give a standard error of 0.058, and a t interval would exclude zero with probability 0.69. Twelve episodes give 0.034 and 0.9999. At r = 1.5 and 2.5, twelve episodes give 0.96 and 0.99. On this count alone, twelve episodes per overlap ratio are enough, as the reviewer proposed, and four are not.

The calibration pool decides the rest. The table gives the probability that the lower end of the adopted interval is above zero (DERIVED; simulation with the moderate episode effect; 2,000 to 4,000 simulated studies per row).

| Calibration pool per prefix per block | FINAL episodes per block | r = 1.5 | r = 2.0 | r = 2.5 |
|---|---|---|---|---|
| 6 × 60 = 360 (v2) | 2 (v2) | 0.53 | 0.82 | 0.90 |
| 6 × 60 = 360 | 6 | 0.57 | 0.86 | 0.95 |
| 6 × 100 = 600 | 6 | 0.80 | 0.98 | 0.99 |
| **12 × 100 = 1,200 (v2.1)** | **6** | **0.93** | **1.00** | **1.00** |
| 12 × 100 = 1,200 | 12 | 0.94 | 1.00 | 1.00 |
| 20 × 100 = 2,000 | 6 | 0.98 | 1.00 | 1.00 |

The pool size moves the power, and FINAL episodes beyond six per block do not. v2.1 therefore doubles the calibration episodes to 12 per block, counts all 100 windows of each, and sets six FINAL episodes per block for each overlap cell, which is 12 pooled.

**Predicted verdict probabilities of the chosen design (DERIVED; simulation, 4,000 simulated studies per setting).**

| Cell | Rule | Strong episode effect (the planning value) | Moderate | Independent windows |
|---|---|---|---|---|
| r = 1.5, 12 episodes | lower end above zero | 0.99 | 0.93 | 0.90 |
| r = 2.0, 12 episodes (primary) | lower end above zero | 1.00 | 1.00 | 1.00 |
| r = 2.5, 12 episodes | lower end above zero | 0.98 | 1.00 | 1.00 |
| r = 3.0, 8 episodes (transition) | upper end at or below 0.05 | 0.48 | 0.36 | 0.35 |
| r = 4.0, 8 episodes | upper end at or below 0.05 | 0.97 | 1.00 | 1.00 |
| r = 5.0, 8 episodes (primary) | upper end at or below 0.05 | 1.00 | 1.00 | 1.00 |

At the predicted peak the interval excludes zero in at least 99.7% of simulated studies under each setting. At r = 3.0 the verdict “against” has a probability below 0.001, so the cell is inconclusive in 52% to 65% of studies. This is why r = 3.0 carries no confirmatory claim.

One limit of the equivalence rule is measured here and not assumed away. At a ratio placed just above the margin (r = 2.75, true drop about 0.06), the rule returns “support” in 0.6%, 3.0%, and 21% of simulated studies for independent windows, the moderate, and the strong episode effect. With few episodes and a strong episode effect, the upper end is therefore not reliable close to the margin. The two H2-volume ratios lie far from it, with predicted drops of 0.0006 and 0.000004.

**Block-agreement rule.** The two block point estimates agree when they fall on the same side of the claim’s reference value. For H2-sensitive the reference is zero, so agreement means the same sign. For H2-volume the reference is the margin: both estimates at or below 0.05 is agreement on the support side, and both above 0.05 is agreement on the against side. Replicated support for H2-volume therefore requires both block estimates to be at or below 0.05. (Round 3, Grok.) A finding is reported as replicated only if the pooled verdict is support and the blocks agree; otherwise it is reported as block-dependent. The v2 condition that the block intervals overlap is dropped, because no interval is computed per block. Under the planning model both block estimates are above zero in 97% to 100% of studies at the three overlap ratios (DERIVED, simulation).

**Descriptive companions (PROPOSED).** Each cell also reports its two block estimates, the paired drop of every episode, the within-episode correlation of the paired difference with the design effect it implies, and the realised benign mean and dispersion of each calibration pool. The realised FPR of each block’s thresholds is estimated on the other block’s calibration pool. None of these changes a verdict.

---

## H. Gates (numeric tolerances; one attempt; saturation rule)

Both gates are written with numeric tolerances so they can be hashed before any study-data vector is read, and the qualification is **one attempt with frozen generator parameters** (no retune-and-retry; a failure is recorded and stops the route). The qualification runs once, before block 1, on its own 13 episodes (section G). The isolation proof and the unique-next-hop gate use no episodes and are repeated at the start of each block, after the reset (PROPOSED). The tolerances are PROPOSED in v2 and unchanged unless marked.

**Qualification gate (tolerances).**

- Generator conformance: per-bot offered-versus-sent within ±2%; aggregate within ±1%; each sender starts within ±50 ms of its scheduled offset; per-1 s-bin rate within ±10% of the plateau target, **checked on plateau bins only**. Ramp bins are covered by the ±1% aggregate check.
- Conservation: ≥ 99.5% of sent attack packets seen exactly once at the OP tap; unmatched records ≤ 0.5%; the full chain planned→sent→tap→meter eligible/selected/retained→records→export→collector reconciles.
- Label identity: the ordered packet rule (section C) assigns every metered packet; 0 packets mislabelled in the fixture cross-check.
- Isolation: 0 egress packets toward any non-lab prefix; the guard counters and route tables match; the unique-next-hop gate passes.
- **Peak-load dry run at the stated aggregate rate.** Three dry-run episodes offer the peak aggregate of 280 pps toward the customer prefixes, which is 240 pps at the target Observation Point (section D-caps): a many-slow SYN flood at r = 5.0 aimed at CUST-1, a few-fast UDP flood at r = 5.0 aimed at CUST-2, and a flash crowd at 240 pps at CUST-1 (PROPOSED compositions). At that rate the interface, qdisc, and veth drop counters show ≤ 0.1% loss at the tap, and send-timing jitter (scheduled minus actual) is within ±20 ms at the 99th percentile. Exceeding either means the virtual machine is **saturated** at that rate.
- **Saturation rule and explicit-rate fallback.** On saturation, the study does not proceed at that rate. It falls back to the next lower pre-registered peak, 160 pps and then 120 pps, **keeping the one-second bins**, or stops if no rate both avoids saturation and keeps a flood shape. The ratio levels above the fallback peak are dropped, with the consequences for the claims stated in section D-caps. No window is widened.

The per-bin band implies paced senders. A Poisson count at 120 pps has a standard deviation of about 11 packets, or 9%, and would leave a ±10% band in about one bin in four (DERIVED). The planning model’s Poisson attack count is therefore the more dispersed bound, and the fixed-count variant in section I is the other bound.

**Feasibility and separability gate on qualification data only.** The primary robust feature, per-prefix packets ×4 scored by the threshold rule, must reach a recall of at least **0.80** at 1% FPR at p0 for each volumetric flood (SYN, UDP, reflection) at r = 3.0. The value 0.80 is frozen here; v2 carried it as “proposed”. Each flood type has two qualification episodes, one aimed at each customer prefix (PROPOSED), and its recall is computed over both, 120 plateau windows, with each window scored against the threshold of its own prefix. The threshold comes from the 4 qualification benign-only episodes, which give 400 windows per prefix, so it is the 5th largest score (DERIVED, P7). The model predicts a recall of 1.000 at this ratio (DERIVED, section I), so the gate tests the generator and the metering, not the statistics. The HTTP flood is exempt; its outcome is recorded. The **per-record arm has its own p0 feasibility stop**: if the per-record template cannot reach ≥ 0.50 recall at 1% FPR at p0 on the qualification data, the per-record arm is reported as infeasible at p0 (not a study failure, a recorded scope limit).

**Stop rules:** isolation or convergence failure, any egress, a customer /24 without a unique next hop, generator non-conformance beyond tolerance, conservation break, saturation with no feasible fallback, a rate above the frozen caps, or a required rate reaching the safety boundary are hard stops. If the volumetric-flood feasibility gate fails at p0 (no non-zero baseline), the study stops and the bounded negative result is reported; the gate is not weakened after the fact.

Pre-registered: the split hypotheses with their decision rules; the seven ratio levels and the ratio-to-claim map; the primary scorer; the feature schema and bin rule; the policy and rescale arms; the operating point, rank rule, and tie rule; the calibration pool; the confirming interval, its resampling units, and the minimum of four episodes per block; the block-agreement rule; the gate thresholds and tolerances; the episode table and counts; the roles of the two points of presence and of the attack types; the TRAIN grid; the FINAL recipient-evaluation mapping; the RQ4 cells and contrasts; the standardization rules; two blocks; and the stop rules. Left to Root: exact per-bot rate seeds and jitter realisation, episode ordering within a block, the bootstrap seed, the exact caps tier after the owner decision, AF configuration, and the FRRouting patch version.

---

## I. Analysis plan and the predicted RQ2 curve

Primary metric: recall at a fixed 1% FPR with the strict rank rule (FROM-SOURCE: v2, the frozen operating point). Primary scorer for H2: the packets ×4 threshold rule. Intervals: the percentile cluster bootstrap over calibration and FINAL episodes (section G). Paired p0-versus-pS on byte-identical packets, matched by (destination, window). Onset and decay (ramp) windows are a **pre-registered secondary analysis** (detection latency), separate from the plateau primary.

**The model (frozen planning values).** The benign count per prefix per one-second bin is negative binomial with mean μ_B = 40 (FROM-SOURCE: v2) and dispersion φ = 0.2 (PROPOSED planning value, frozen by the v2.1 brief), so its variance is 40 + 0.2 × 40² = 360 (DERIVED). The attack count in an attack bin is Poisson with mean r × 40 and independent of the benign count (PROPOSED modelling assumption). Under pS each packet is kept with probability 1/4, and the score is four times the kept count. The benign sampled count is then negative binomial with mean 10 and the same dispersion (P4), the attack sampled count is Poisson with mean 10r (P5), and the rescaled benign variance is 360 + 3 × 40 = 480 (P3).

**Thresholds (DERIVED, exact).** The 0.99 quantile of the benign score is 96 under p0 and 104 under pS, which is 26 sampled packets. The Gaussian approximation in v2 gave 84. With the strict tie rule the achieved FPR is 0.96% under p0 and 0.93% under pS.

**Predicted recall of the volume scorer (DERIVED, exact sums of the mass functions).**

| r = A/μ_B | A (pps) | Recall p0 | Recall pS (own threshold) | p0→pS drop | Recall, train p0 / test pS **unscaled** |
|---|---|---|---|---|---|
| 1.0 | 40 | 0.189 | 0.148 | 0.041 | 0.000 |
| 1.5 | 60 | 0.523 | 0.378 | 0.145 | 0.000 |
| 2.0 | 80 | 0.885 | 0.671 | 0.214 | 0.000 |
| 2.5 | 100 | 0.994 | 0.883 | 0.111 | 0.000 |
| 3.0 | 120 | 1.000 | 0.972 | 0.028 | 0.000 |
| 4.0 | 160 | 1.000 | 0.999 | 0.001 | 0.000 |
| 5.0 | 200 | 1.000 | 1.000 | 0.000 | 0.000 |

On a grid of 0.05 the drop peaks at r = 1.95 with 0.2155, and it falls to 0.05 at r = 2.85. The curve keeps the shape that v2 described, a drop only where the two distributions overlap, but the peak sits at r ≈ 2 and not at r ≈ 1.5, and r = 1.0 carries little drop. The **unscaled mismatch arm collapses to a recall of about zero at every ratio of the sweep, including r = 5**: the largest value is 0.0003, at r = 5.0. The sampled counts are about one quarter of the trained scale and stay below the p0 threshold.

**Root’s check reproduced.** The exact values agree with Root’s five simulated rows. The largest difference is 0.0018, for the p0 recall at r = 1.5 (0.5228 exact against 0.521), which is about two Monte Carlo standard errors of a 400,000-draw estimate once the rounding of the reported figure is allowed for. The exact threshold is 96, as Root found. A Monte Carlo run in the script with seed 0 and 400,000 draws gives 0.188 / 0.147, 0.524 / 0.378, 0.885 / 0.672, 1.000 / 0.972, and 1.000 / 1.000 for the p0 and pS recall at r = 1.0, 1.5, 2.0, 3.0, 5.0. Root’s own script was not available, so the comparison is statistical.

**Frozen p0 threshold under pS (DERIVED, exact).** Applying the p0 threshold of 96 to the rescaled pS benign count raises the FPR from 0.96% to **1.61%**. v2 gave 2.2% from the Gaussian formula. At a dispersion of 0.1 the value is 3.1%, where v2 gave 3.3%. This stays the reported FPR-change arm.

**Sensitivity of the map to the planning values (DERIVED, exact).** The position of the peak follows the benign dispersion.

| Dispersion φ | r = 1.0 | 1.5 | 2.0 | 2.5 | 3.0 | 4.0 | 5.0 |
|---|---|---|---|---|---|---|---|
| 0.10 | 0.233 | 0.332 | 0.147 | 0.034 | 0.005 | 0.000 | 0.000 |
| 0.15 | 0.077 | 0.215 | 0.181 | 0.057 | 0.010 | 0.000 | 0.000 |
| **0.20** | **0.041** | **0.145** | **0.214** | **0.111** | **0.028** | **0.001** | **0.000** |
| 0.25 | 0.031 | 0.104 | 0.207 | 0.172 | 0.061 | 0.002 | 0.000 |
| 0.30 | 0.025 | 0.077 | 0.175 | 0.215 | 0.111 | 0.006 | 0.000 |

For a dispersion between 0.10 and 0.30, at least two of the three overlap ratios keep a predicted drop of 0.10 or more, and r = 4.0 and 5.0 stay far inside the margin. The drop at r = 3.0 crosses the margin between a dispersion of 0.20 and 0.25, which is a second reason why r = 3.0 carries no confirmatory claim. Two other inputs matter less. A fixed attack count in place of a Poisson one changes the drop at r = 2.0 from 0.214 to 0.243 and at r = 2.5 from 0.111 to 0.099. A benign mean of 30 or 50 changes the drop at r = 2.0 to 0.240 or 0.192.

The map is frozen by ratio level at φ = 0.2. The build targets the planning values for the benign generator in DEV, before the qualification attempt. The realised mean and dispersion of each calibration pool are reported, and the same script is rerun at the realised values as a descriptive companion. The map is not changed after FINAL data.

**Finite calibration pools.** With thresholds estimated from the planned pool of 1,200 windows, the realised thresholds and false-positive rates differ from the exact ones, most under the strong episode effect. There the mean p0 threshold is 88.6 rather than 96, the mean realised false-positive rate is 2.5%, and its 5th to 95th percentiles are 0.23% to 6.5%; under the moderate effect the figures are 94.5, 1.2% and 0.46% to 2.1%, and with independent windows 95.5, 1.0% and 0.64% to 1.6% (DERIVED, Root simulation, seed 20261115, 20,000 studies, 12 × 100 calibration windows, rank rule k = 13). The mean drop estimates are biased accordingly; at the primary ratio the bias is toward zero. The realised false-positive rate of each block is therefore reported beside every recall, as a measured quantity. The episode counts do not change, because the verdict probabilities already include this bias. (Round 3, Grok.) Across the three simulation settings they are 0.16 to 0.21 at r = 1.5, 0.19 to 0.22 at r = 2.0, 0.09 to 0.12 at r = 2.5, and 0.03 at r = 3.0 (DERIVED, simulation).

**Distinct source hosts, predicted from the bin total (DERIVED, P6).** The prediction assumes 120 benign sources that share 40 pps and emit independently within a bin. A benign-only bin then shows about 34.0 distinct hosts under p0 and 9.6 under pS. An attack bin holds those benign hosts plus the bots that emit in the bin.

| r | Configuration | Attack hosts added, p0 | Attack hosts added, pS | Attack-bin total, p0 | Attack-bin total, pS |
|---|---|---|---|---|---|
| 2.0 | many-slow (120 bots) | 58.4 | 18.4 | 92.4 | 28.0 |
| 2.0 | few-fast (24 bots) | 23.1 | 13.6 | 57.2 | 23.2 |
| 5.0 | many-slow | 97.3 | 40.9 | 131.4 | 50.5 |
| 5.0 | few-fast | 24.0 | 21.0 | 58.0 | 30.6 |

In both configurations and under both policies the attack bin holds more distinct hosts than the benign bin. The feature therefore separates in the same direction for many-slow and few-fast. v2 said “opposite directions” because it compared the attack hosts alone with the benign hosts, and that statement is withdrawn. Many-slow adds more hosts than few-fast, and sampling narrows the difference between them.

How much recall a distinct-host rule loses under pS is not fixed by the planning model, because it depends on how the benign sources share the variation of the benign rate. Two bounding cases show the range at r = 2.0 (DERIVED). If the sources vary independently, the recall of a distinct-host threshold rule is 1.000 under p0 and 0.987 under pS for many-slow, and 0.985 and 0.934 for few-fast. If all sources follow one common rate, which is the case that reproduces the negative-binomial count exactly, it is 0.968 and 0.690 for many-slow, and 0.195 and 0.365 for few-fast. In that last case sampling raises recall, because it removes one-packet benign hosts faster than multi-packet bots. The structural claim is therefore estimation only: the paired p0-to-pS change for distinct hosts is reported with its interval for each configuration, without a predicted sign for few-fast.

The **per-record arm** degrades under pS by the collision ceiling (P13).

**What is reported.** The RQ2 deliverable is the curve of p0 and pS recall against r, per feature family and per bot configuration, with the ratios at which sampling starts and stops costing recall read off each curve. Multiplicity is controlled by naming the primary cells: H2-sensitive at r = 2.0 for the SYN flood and for the UDP flood, and H2-volume at r = 5.0. Every other cell is secondary and labelled so. RQ1 is federation versus local, pooled, and AF at 1% FPR under p0; RQ4 is the contrasts D_C, D_E, D_CE of section A3 at a fixed contributor count and pre-policy volume.

---

## J. Threats to validity and stated limits

**Attack-rate stability between episodes.** The power simulation and the cluster bootstrap attribute between-episode variance to the benign rate only; the attack count is Poisson with the same mean in every episode. Episode-level attack-rate deviations are bounded by the generator qualification tolerance (per bot within ±2%, aggregate within ±1%, and the ±10% plateau band of section G) rather than modelled. Larger jitter would widen the intervals, and the per-episode attack counts are recorded so that it can be checked. (Round 3, Gemini.)

Internal: one kernel and one clock; bots are not independent attackers; timing is one lab time base (checked at peak by the dry run). Generator fingerprints could separate classes for non-attack reasons; the same-protocol, same-port, realistic-option-set construction and the calibrated benign reduce but do not remove this, so feature-support diagnostics are reported. Windows within an episode are dependent; intervals are episode-clustered.

Calibration (new in v2.1): a 1% FPR threshold is estimated from a finite benign pool, and its noise is the largest part of the block-to-block variation of the paired drop. With 1,200 windows and a moderate episode effect, the realised FPR of the p0 threshold lies between about 0.5% and 2.1% in nine simulated studies out of ten. A strong episode effect biases the rank threshold low, with a mean realised FPR of 2.5% under p0 (DERIVED, simulation). The confirming interval resamples the calibration episodes for this reason, and the realised FPR is reported from the other block’s pool. The equivalence rule is not reliable close to its margin when the episode effect is strong (section G). Intervals for learned-model contrasts are conditional on the trained models, because TRAIN episodes are not resampled; the spread across seeds is reported beside them.

Planning model: the ratio-to-claim map rests on a benign dispersion of 0.2. If the realised dispersion differs, the peak moves (section I); the map stays as frozen and the recomputed predictions are reported beside the results.

Construct: no-spoof reflection reproduces only the victim-side observable; HTTP flood may be indistinguishable from a same-rate legitimate crowd (honest negative pre-registered); the emulated botnet is a controlled emulation, not a botnet; labels are intent plus conformance.

External: IPv4 only; three /24 blocks give only three /24 source prefixes and about 576 host addresses across nine /26 sites after the infra reservation (DERIVED in the topology file), far short of a real botnet; a single OSPF area and three transit autonomous systems simplify a real ISP; if the static-routing fallback is taken, there is no dynamic routing and no control-plane traffic, a further step from reality; rates are bounded well below real floods by the safety caps; two points of presence are a minimal federation. All FINAL attacks are aimed at the recipient’s prefix, so the sampled-versus-unsampled comparison is made at one of the two symmetric meters; the roles of the two points of presence are fixed, so role and site are confounded.

---

## K. Literature needs

Unchanged from v2. Held and read: Duffield et al. 2002; Brauckhoff et al. 2006; Mai et al. 2006; Roudière and Owezarski 2018; Kopmann and Zitterbart 2023; and the FL-for-IDS set Sarhan et al., Djaidja et al., Sellier and Martini. To verify from local records before the owner is asked, no web use: Antonakakis et al. 2017 (Mirai rates), a botnet-characterisation source, Rossow 2014 (amplification gains, to set the frozen reflection gain), and an HTTP/application-layer flood source. Root checks each identity.

---

## L. Work plan and ETA

Unchanged in structure from v2: design and final check (this step); owner decisions; freeze and hash the definitions; a build worker builds the topology, FRRouting (or the static fallback), bots, benign clients, responders, metering, collector, and adapter (no attack-packet fixtures by the design worker; subject to the safety boundary); Root runs the one-attempt qualification gate including the peak-load dry run; acquisition over two blocks, double-metered; analysis with the cluster-bootstrap intervals; write-up. The ETA stays at about **12–20 working days** of attended work from the owner’s go-ahead (PROPOSED estimate, as in v2), spread over more calendar time. The larger episode table adds about 2.3 hours of offered traffic (DERIVED: 7.5 against 5.2). Correctness over the December target, which the owner has set as not a hard limit.

---

## M. Propositions (stated for the Lean check)

`PROPOSITIONS-FOR-LEAN.v2.1.md` states each proposition the design cites, marks it as an elementary fact, a numeric result only, or already machine-checked, and gives a proof idea. Root assigns the Lean check; the design worker wrote no Lean. The idealization for P1 to P6 is the one in v2: the HMAC-SHA256 1-in-4 selector keeps each eligible packet independently with probability 1/4, which treats the keyed hash as a random function and is not proved here.

| Label | Content | Class |
|---|---|---|
| P1 | The rescaled count 4S is unbiased, for packets, bytes, and SYN packets | elementary |
| P2 | Var(4S given P packets) = 3P; coefficient of variation √(3/P); the byte estimator’s factor √(b_max/b_avg) is a variance factor, not a bias | elementary |
| P3 | Var(4S) = Var(N) + 3·E[N] for a random count N; 360 becomes 480 | elementary; the two numbers are numeric |
| P4 | Binomial thinning of a negative binomial is negative binomial with the same size | elementary |
| P5 | Binomial thinning of a Poisson is Poisson; the selected benign and attack parts are independent | elementary |
| P6 | Distinct hosts: a host with k packets is missed with probability (3/4)^k; no constant corrects the count; occupancy n(1 − e^(−Λ/n)) | elementary |
| P7 | The rank-rule threshold keeps the calibration FPR at or below 1%; expected FPR on new windows | elementary |
| P8 | Mean and variance of the paired alert difference | elementary |
| P9 | Design effect 1 + (m − 1)ρ of a cluster mean | elementary |
| P10 | An additive gamma split keeps the negative-binomial margin (used by the simulation) | elementary |
| P11 | Logic of the equivalence and exclusion rules, given an interval with stated coverage | elementary; the coverage of the bootstrap interval is numeric only |
| P12 | Standardization removes a common scale factor | elementary |
| P13 | Per-record recall ceiling `recall_ceiling` (v2’s Proposition 4), scope unchanged | already machine-checked, FROM-SOURCE |

The thresholds, the recall table, the FPR values, the design effects, the distinct-host numbers, and every power or size figure are numeric results only. The two thresholds and the three FPR values are finite sums of rationals and can be certified exactly; the script checks them with exact fractions.
