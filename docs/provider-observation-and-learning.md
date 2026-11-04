# Provider observation and learning choices

Updated November 4, 2026.

Provider-operated detection can use measurements from several network locations
without requiring a separate detection appliance at each customer site. The
current assessment compares customer-facing provider-edge (PE) observations with
Internet-border observations. It separates where packets are observed, where
flow records are collected, where a model is trained, where inference runs and
where mitigation acts. These are proposed design choices, not a completed
network experiment or a revised final protocol.

## Observation does not determine model placement

[RFC 5470](https://www.rfc-editor.org/rfc/rfc5470.html), Sections 2, 4 and 5,
distinguishes observation, metering, export and collection. A collector can
receive records from multiple exporters. Central analytics therefore need not
mean a single physical observation point or an inline packet bottleneck. The
RFC is an informational architecture document, updated by RFC 6183 on mediation;
it does not prove that a particular exporter supports the required egress
measurement or fields.

A customer-facing PE view can identify a customer’s traffic when interface and
routing context are retained. However, its meaning depends on the actual
metering stage. An egress record must not be treated automatically as proof of
post-queue delivery to the CE. Earlier congestion or drops can also limit what
is observed. Internet-border measurements offer a different view of externally
offered load. Earlier observation does not by itself prove an earlier alert.
These are information-limit checks for the proposed comparison, not measured
outcomes.

The [NETSCOUT design example](https://www.netscout.com/sites/default/files/2020-09/SECJTF_003_EN-2001%20-%20Arbor%20Sightline%20-%20How%20It%20Works.pdf),
pp. 1–3, describes provider-wide analytics using flow, BGP and SNMP data,
customer/service monitoring, and separate upstream mitigation actions. This
2020 vendor document illustrates an existing deployment pattern. It is not an
independent performance comparison or a choice of software for this lab.

## Compare centralized and federated learning fairly

A centrally trained model can run inference at provider locations. Local
inference alone therefore does not establish a need for federated learning.
[Pourahmadi et al. (2023)](https://doi.org/10.1109/TDSC.2022.3224896) already
compare cloud-centralized, edge-local and federated approaches. Section 5.6 and
Figure 5 of the inspected author manuscript describe a centrally trained model
used for edge-server detection. Their results are specific to that setup.

| Candidate | Question for the unrun comparison |
|---|---|
| PE observations with pooled training | Does permitted central pooling provide a sufficient baseline, including local inference? |
| Same PE observations with local training and model exchange | Does federation provide a measured quality or cost advantage over pooled and local-only training? |
| Internet-border observations with central analysis | What externally offered traffic is visible when all relevant borders are covered? |
| Combined border and PE observations | Does additional coverage justify its collection cost after provenance and overlapping records are handled? |

Pooling depends on permission, governance and operational constraints, not only
on common provider ownership. Federation should be justified against the actual
objectives. Keeping records local does not itself provide a formal privacy
guarantee ([Kairouz et al., 2021](https://doi.org/10.1561/2200000083)).
Transmission savings also require measurement. The comparison should account for serialized telemetry,
model exchange and update cadence over the declared training lifecycle.

Learning methods should first be compared with the same observation inputs.
Changing the observation location at the same time would mix information and
learning effects. Separate checks must establish exporter behavior, sampling,
record loss, feature compatibility, inference placement and end-to-end alert
timing before conclusions are drawn.

## Assessment status

A bounded xAI Grok critique of public architecture concepts and source summaries
informed this assessment. The tool reported `grok-4.7-build`. The writer accepted
the central baseline and the separation of design choices, then qualified
pooling permission, metering-stage semantics and alert-timing claims. The review
had no RAG, web or execution access. It does not validate the lab, select the
final protocol or certify novelty.

No EVE topology was rebuilt, no new training was run and no empirical comparison
is reported here. The earlier version-1 lab drawing remains design history.
Scientific code remains at its existing reviewed commit. The
[Research hub](https://oliabak.com/research/federated-ddos/) records continuing
project status; private drafts and detailed study decisions remain outside this
public note.

## References

- Kairouz, P., McMahan, H. B., Avent, B., Bellet, A., Bennis, M., Bhagoji, A. N., ... Zhao, S. (2021). Advances and open problems in federated learning. *Foundations and Trends in Machine Learning, 14*(1–2), 1–210. <https://doi.org/10.1561/2200000083>
- NETSCOUT. (2020). *Arbor Sightline: How it works and where it lives in the network*. Retrieved from <https://www.netscout.com/sites/default/files/2020-09/SECJTF_003_EN-2001%20-%20Arbor%20Sightline%20-%20How%20It%20Works.pdf>
- Pourahmadi, V., Alameddine, H. A., Salahuddin, M. A., & Boutaba, R. (2023). Spotting anomalies at the edge: Outlier exposure-based cross-silo federated learning for DDoS detection. *IEEE Transactions on Dependable and Secure Computing, 20*(5), 4002–4015. <https://doi.org/10.1109/TDSC.2022.3224896>
- Sadasivan, G., Brownlee, N., Claise, B., & Quittek, J. (2009). *Architecture for IP flow information export* (RFC 5470). RFC Editor. Retrieved from <https://www.rfc-editor.org/rfc/rfc5470.html>
