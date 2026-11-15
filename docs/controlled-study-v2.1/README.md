# Controlled study design v2.1 (pre-registered, not run)

This folder publishes the frozen design of a new controlled laboratory study for the thesis. The study asks how packet sampling at a provider’s border routers changes what a router-side detector can see during flood-shaped DDoS attacks (RQ2), and how detection at a recipient point of presence changes when it collaborates with a second, contributing point of presence (RQ1 and RQ4). The design was frozen on November 15, 2026, before any build, traffic or data. Nothing in this folder is a measurement.

## Status

The study is designed and frozen. No laboratory component has been built or started, and no traffic has been generated. Building the laboratory, qualifying it, and acquiring data are later steps, and each needs a separate release by the researcher. The earlier controlled track stopped at its pre-registered separability gate. That result stays reported unchanged; this study is a separate, newly pre-registered study and does not replace it.

## Files

The design files are byte-identical to the frozen copies. Their SHA-256 values match the private freeze record.

| File | Content | SHA-256 |
|---|---|---|
| `DESIGN.v2.1.md` | Hypotheses, topology summary, traffic, routing, safety caps, features, models, episodes, gates, analysis plan, threats and propositions | `3f720f685c4d7558f84e7f0750caf966b8e28c2e93206725e539917c53cc7645` |
| `TOPOLOGY-IP-PROPOSAL.v2.1.md` | Address plan, autonomous systems, links and routing | `ae9c70c86afbb392ddc1953662af316dcec85ddbf32619a50be1a5235b01cb4c` |
| `PROPOSITIONS-FOR-LEAN.v2.1.md` | Propositions P1 to P12 as stated for the formal check | `a997a7366d7d7e814fd1c8cd9c13fef078d5d2f70403472a94bf3bb42c50c80f` |
| `federated-ddos-topology.v2.2.svg` | Topology figure, version 2.2 | `e051fb45faaddbc6d40aed7945c1490b50f14a153fe1b4fa8b0ceea1e5da33aa` |
| `caption.v2.2.txt` | Figure caption | `cf3d7fc946d90433d6e958aa2ba0569fc9eb598071eb9d79364ee2d1b9dec8c6` |

## How to read the frozen files

The files were written for the design review and kept unchanged when the design was frozen. Three consequences follow for a reader.

- The status line of `DESIGN.v2.1.md` still says “design only” and “not a freeze”, and the figure caption still says “proposal for owner review”. Both texts predate the freeze. The researcher then decided the open items and approved the topology and addresses after viewing version 2.2 of the figure, and the design was frozen.
- The design refers to sibling files that are not published here: the review packet, the responses to the reviews, the decision list, a machine-readable copy, and the planning computation. These are private working records. The planning computation is a seeded statistical model of per-bin packet counts and creates no traffic; its figures are quoted in sections G and I with the label DERIVED.
- Every number in the design carries a label. DERIVED marks a computed value, FROM-SOURCE marks a value taken from a cited record, and PROPOSED marks an engineering choice with its reason.

The researcher fixed the open values as follows. The peak offered rate is 200 packets per second per victim, at most 20 per bot, at most 400 for all attack traffic, and 280 in aggregate for the dry run, with a kill switch and a study ceiling of 4.0 million offered packets. Reaching a safety limit stops the study, and the pre-registered fallback peaks are 160 and then 120 packets per second with one-second bins kept. Routing is eBGP between the border and transit routers and OSPF area 0 inside, on pinned FRRouting, with no redistribution and a static-routing fallback chosen before any data. Reflection uses at least 24 scripted in-lab responders that answer from their own addresses; no address is spoofed. The laboratory is IPv4 only and uses private autonomous system numbers 64512 to 64515 and the three RFC 5737 documentation blocks outside the provider.

## Safety boundary

The whole laboratory is planned inside one isolated virtual machine with no route out, no network address translation and IPv6 disabled. The detector observes only; it does not filter or mitigate. Every traffic source is a scripted process on one computer, so the study cannot show distributed attack impact or Internet-scale behaviour. No generator code, packet bytes or attack fixtures are published here.

## Formal check

Propositions P1 to P12 are checked in the [Lean project](../../formal-verification/README.md), module `ThesisVerification/ControlledDesign.lean`, with 124 theorems. The [verification record](../lean-verification.json) lists the axioms of every theorem and the hashes of the checked files. One wording change was made after the check. Statement (c) of P6 now begins “For 0 < p < 1”, because at p = 1 the constant 1 is exact (theorem `p6c_constant_at_one`). The formal statement already assumed p ≠ 1. The source map `design-source-map.json` therefore records the hash of the propositions file before this change, `834227af06dd9256ff67469f5b30abd825d2a808ee50689c01d5da8f4efb13b4`.

The formal check has stated limits. P4 is proved for an integer negative-binomial size only. P6 (d), P7 (b) and P9 are proved on finite sample spaces. For P10 only the covariance identities are proved; the sum of two Gamma variables, the Poisson–Gamma mixture and the Gamma variance are not formalized. The keyed packet selector is treated as independent selection without proof. Simulated values and values of e^(−λ) remain numerical results, not theorems.

## What this design does not establish

A frozen design establishes what will be measured and how the results will be judged. It does not establish detection performance, the effect of sampling, the benefit of collaboration, or the behaviour of a real provider network. Those questions remain open until the study is built, qualified and run, and its results are analyzed under the pre-registered rules.
