# Foundational reference selection

Updated November 3, 2026.

This supplement establishes the terms needed to understand the study before its
specific comparisons are presented. The reading sequence begins with service
availability and DDoS, then identifies the learning task, available labels,
models, gradient training and federated coordination. A broad history of AI or
a reinforcement-learning experiment is outside this bounded supplement. The
[Research reference library](https://oliabak.com/research/federated-ddos/references.html)
provides the selected public bibliography and original publication links.

## Selection procedure and evidence roles

The project reused relevant references already in its working library, then
added sources for concepts that needed an original or established account.
Selection considered the source’s relevance, primary publication identity,
accessible evidence and the specific explanation it supports. Citation influence
was used only as a secondary discovery aid. It does not establish quality,
correctness, novelty or suitability for the proposed experiment.

The eight scholarly additions bring the retained reading bank from 87 to 95
works. The working Zotero collection has 98 parent references because it also
includes three supporting records for engineering use cases and contemporary
measurement. These counts describe different units. The earlier 87-record
collection-year chart remains a historical snapshot. None is a count of
independent replications or evidence of field-wide scarcity.

The new reading was targeted to the definitions and mechanisms used in the
opening and foundations. It is separate from the original 71-source appraisal
batch and does not establish a new exhaustive systematic review. Exact reading
limits remain in the private source register. The
[critical literature review workflow](critical-literature-review.md) describes
how those limits and counterevidence are recorded.

| Source | Purpose | Targeted evidence and boundary |
|---|---|---|
| Mirkovic and Reiher (2004) | DDoS terminology and taxonomy | Section 2 and the Section 3 victim types. Historical mechanisms, not current attack prevalence. The journal paper has two authors. |
| Jordan and Mitchell (2015) | Orientation to machine learning | Printed pp. 255, 257–258. Does not select a DDoS learner or establish superiority over other methods. |
| LeCun, Bengio and Hinton (2015) | Neural representations and backpropagation | Printed pp. 436–437. Model architecture, label availability and optimizer remain separate choices. |
| Chandola, Banerjee and Kumar (2009) | Anomaly detection and score-to-decision roles | Sections 1.1–1.2 and 2.3–2.4. Terminology for normal-only fitting must be defined in the actual workflow. |
| Kairouz et al. (2021) | Organization-level federated learning | arXiv v3 introduction, Table 1 and Section 2.2. Typical cross-silo properties are not universal requirements or privacy guarantees. |
| Bottou, Curtis and Nocedal (2018) | Gradient training and optimization | Author preprint Sections 2.2, 3.2 and 4. Theoretical conditions do not automatically apply to a proposed detector. |
| Rumelhart, Hinton and Williams (1986) | Early backpropagation reference | Publisher abstract and first printed page. Individual scanned equations were not checked; no invention-priority claim is made. |
| Mirsky et al. (2018) | Concrete reconstruction-based network detection example | Section III and Figures 1–2. Supports an illustrative autoencoder, not a final backbone choice or provider-scale throughput claim. |

Existing references such as McMahan et al. for FedAvg, Kingma and Ba for Adam,
and Lavaur’s dissertation retain their own reading records. Reusing them does
not enlarge the new-source count. The focused route separates the detection
problem from model architecture, local optimization and collaboration. A
foundational citation does not establish that collaboration improves detection
or that the study is novel.

The three supporting records have different roles. RFC 8903 is informational
engineering guidance on provider and mitigation use cases. Cloudforce One’s
Q3 2026 report supplies explicitly attributed operational observations, and
Cloudflare’s measurement page explains the report’s counting method. Provider
telemetry is not a worldwide count of independent attack campaigns, a
peer-reviewed FL experiment or evidence that FL helps. No numerical telemetry
claim is required to use these records as reading references.

Independent reviewers received the same frozen, bounded public-source packet.
The packet contained bibliography, targeted evidence and generic study
requirements, with no chapters, credentials, correspondence or raw observations.
The project records actual reviewer availability, model identity when exposed,
recommendations and the writer’s resolution. The separate Antigravity and xAI critiques returned no blocking findings.
Antigravity selected Claude Opus 4.6 Thinking; its serving identifier was not
exposed. xAI reported `grok-4.7-build`. A Grok output-contract retry is recorded
separately from its completed review. The writer checked their advice against
source and artifact records. Agreement is not scientific validation. The final learner, protocol, novelty assessment and empirical
results retain their separate checks.

## References

Bottou, L., Curtis, F. E., & Nocedal, J. (2018). Optimization methods for large-scale machine learning. *SIAM Review, 60*(2), 223–311. <https://doi.org/10.1137/16M1080173>

Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly detection: A survey. *ACM Computing Surveys, 41*(3), Article 15. <https://doi.org/10.1145/1541880.1541882>

Cloudflare. (2026). *Quarterly DDoS threat reports*. Retrieved November 3, 2026, from <https://developers.cloudflare.com/radar/reference/quarterly-ddos-reports/>

Cloudforce One. (2026, October 29). *Cloudflare DDoS threat report 2026 Q3: More swarms, fewer giants*. <https://blog.cloudflare.com/ddos-threat-report-2026-q3/>

Dobbins, R., Migault, D., Moskowitz, R., Teague, N., Xia, L., & Nishizuka, K. (2021). *Use cases for DDoS open threat signaling* (RFC 8903). RFC Editor. <https://doi.org/10.17487/RFC8903>

Jordan, M. I., & Mitchell, T. M. (2015). Machine learning: Trends, perspectives, and prospects. *Science, 349*(6245), 255–260. <https://doi.org/10.1126/science.aaa8415>

Kairouz, P., McMahan, H. B., Avent, B., Bellet, A., Bennis, M., Bhagoji, A. N., ... Zhao, S. (2021). Advances and open problems in federated learning. *Foundations and Trends in Machine Learning, 14*(1–2), 1–210. <https://doi.org/10.1561/2200000083>

LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. *Nature, 521*(7553), 436–444. <https://doi.org/10.1038/nature14539>

Mirkovic, J., & Reiher, P. (2004). A taxonomy of DDoS attack and DDoS defense mechanisms. *ACM SIGCOMM Computer Communication Review, 34*(2), 39–53. <https://doi.org/10.1145/997150.997156>

Mirsky, Y., Doitshman, T., Elovici, Y., & Shabtai, A. (2018). Kitsune: An ensemble of autoencoders for online network intrusion detection. In *Proceedings of the Network and Distributed System Security Symposium*. Internet Society. <https://doi.org/10.14722/ndss.2018.23204>

Rumelhart, D. E., Hinton, G. E., & Williams, R. J. (1986). Learning representations by back-propagating errors. *Nature, 323*(6088), 533–536. <https://doi.org/10.1038/323533a0>
