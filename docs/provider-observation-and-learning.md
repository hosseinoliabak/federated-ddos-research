# Provider observation and learning choices

Updated November 4, 2026.

The provisional provider-operated design places collection and scoring at provider
points of presence (PoPs), with central coordination. It does not assume detector
appliances on customer premises. Internet-border ingress is the primary
observation candidate for externally offered load. Customer-facing provider-edge
(PE) views remain complementary or a separate observation comparison.

Observation, flow collection, training, inference and mitigation remain separate
decisions. Local-only, permitted pooled-central and federated training should be
compared on matched inputs. Reporting by customer does not, by itself, define
the training participants. These are proposed choices, not a selected final
protocol or a completed experiment.

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
compare cloud-centralized, edge-silo and federated approaches. Section 5.6 and
Figure 5 of the inspected author manuscript describe a centrally trained model
used for edge-server detection. Their results are specific to that setup.

| Candidate | Check for the unrun comparison |
|---|---|
| Internet-border observations with central analysis | Cover all relevant borders and establish which externally offered traffic is visible. |
| Customer-facing PE views | Check customer context, metering stage and missing information before treating these as complementary or alternative inputs. |
| Matched observations with local-only, pooled-central or federated training | Compare quality and cost with equivalent inference placement and permitted information access. |
| Combined border and PE observations | Establish provenance and handle overlapping records before assessing additional coverage and cost. |

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

## Existing precedents

Published precedents already cover parts of this architecture. [RFC 9387 (2023)](https://www.rfc-editor.org/rfc/rfc9387.html), Sections 3.1 and 3.3, describes forwarding nodes, IPFIX flow collectors, orchestration and machine-learning feedback. The institutional abstract for [FlowSentry (He et al., 2025)](https://researchconnect.stonybrook.edu/en/publications/flowsentry-accelerating-netflow-based-ddos-detection/) reports server-side analysis of partially reported NetFlow using cross-router relationships to address detection delay; this assessment inspected that abstract, not a full-paper appraisal. Multi-point collection or hierarchy alone therefore does not establish novelty.

## Assessment status

Two bounded xAI Grok critique rounds on public architecture concepts and source
summaries informed this assessment. The tool reported `grok-4.7-build`. The writer accepted
the central baseline and the separation of design choices, then qualified
pooling permission, metering-stage semantics and alert-timing claims. The review
had no RAG, web or execution access. It does not validate the lab, select the
final protocol or certify novelty.

Scalability remains an evaluation goal. Any proposed mechanism needs measured
quality/cost improvements and full-text comparison with the closest precedents
before a novelty claim. No EVE topology was rebuilt, no new training was run and
no empirical comparison is reported here. The earlier version-1 lab drawing remains design history.
The [reviewed scientific code](https://github.com/hosseinoliabak/federated-ddos-research/tree/102293e69f2f9e7cdcac58cb12ffe8d7d0165833) remains unchanged. The
[Research hub](https://oliabak.com/research/federated-ddos/) records continuing
project status; private drafts and detailed study decisions remain outside this
public note.

## References

- Hayashi, Y., Chen, M., & Su, L. (2023). *Use cases for DDoS open threat signaling (DOTS) telemetry* (RFC 9387). RFC Editor. Retrieved from <https://www.rfc-editor.org/rfc/rfc9387.html>
- He, X., Xie, X., Wang, X., Zhang, L., Xie, K., Chen, L., & Cui, Y. (2025). FlowSentry: Accelerating NetFlow-based DDoS detection. In *Proceedings of the 2025 ACM SIGSAC Conference on Computer and Communications Security* (pp. 1589–1603). Association for Computing Machinery. <https://doi.org/10.1145/3719027.3744800>
- Kairouz, P., McMahan, H. B., Avent, B., Bellet, A., Bennis, M., Bhagoji, A. N., ... Zhao, S. (2021). Advances and open problems in federated learning. *Foundations and Trends in Machine Learning, 14*(1–2), 1–210. <https://doi.org/10.1561/2200000083>
- NETSCOUT. (2020). *Arbor Sightline: How it works and where it lives in the network*. Retrieved from <https://www.netscout.com/sites/default/files/2020-09/SECJTF_003_EN-2001%20-%20Arbor%20Sightline%20-%20How%20It%20Works.pdf>
- Pourahmadi, V., Alameddine, H. A., Salahuddin, M. A., & Boutaba, R. (2023). Spotting anomalies at the edge: Outlier exposure-based cross-silo federated learning for DDoS detection. *IEEE Transactions on Dependable and Secure Computing, 20*(5), 4002–4015. <https://doi.org/10.1109/TDSC.2022.3224896>
- Sadasivan, G., Brownlee, N., Claise, B., & Quittek, J. (2009). *Architecture for IP flow information export* (RFC 5470). RFC Editor. Retrieved from <https://www.rfc-editor.org/rfc/rfc5470.html>
