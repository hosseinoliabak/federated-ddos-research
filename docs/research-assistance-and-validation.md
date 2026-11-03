# Research assistance and validation

This workflow documents research assistance without treating assistance as
scientific evidence. It keeps the researcher’s responsibility, the actual tool
use, and the checks supporting each claim visible. It is a reusable project
procedure, not an institutional approval or a completed validation report.

## Describe assistance in proportion to its use

Keep a concise disclosure in the manuscript and a more detailed task record.
Describe the tools, purposes, and affected work accurately. Depending on the
recorded task, assistance can include paper discovery, source-extraction and
appraisal drafts, criticism of research framing, manuscript drafting and
revision, code, illustrations, or organization. Describe substantive drafting
and coding when they occurred; describing all assistance as proofreading would
understate that work.

The author remains responsible for the research choices, interpretation, and
submitted text. Working material still requires the author’s review and
acceptance. Do not claim that the author has checked every passage or artifact
when that review is still pending. Similarly, do not assign an unmeasured
percentage of authorship to a tool.

Tool-suggested papers are retrieval leads. Verify bibliographic identity and
consult the relevant primary passages before using a paper to support a claim.
Retain the recorded limits when only an abstract, selected section, or incomplete
text was accessible. The [literature-review workflow](critical-literature-review.md)
records those distinctions.

For an ÉTS thesis, discuss the permitted uses and conditions with the research
director, and describe which tools were used, how, and why. The director may
also require a foreword statement. These requirements come from the
[ÉTS thesis-writing guide](https://www.etsmtl.ca/en/study-at-ets/graduate-studies/graduate-studies-office/drafting-guide-report-dissertation-thesis#generative-ai-system-genai),
consulted November 3, 2026. This workflow does not record an individual approval.

## Record separate model critiques

Submit the same bounded packet separately to each reviewer when the task calls
for independent critiques. Record the packet hash, permitted source access,
provider, requested model, reported model if exposed, date, response, and the
resolution of material comments. Separate submissions do not establish
statistical independence, and reviewers can share errors or assumptions.

Keep completed, planned, unavailable, and timed-out reviews distinct. Record a
new model version only when that version actually performs the review. A future
review must not relabel earlier work, and a provider name must not be expanded
into an unrecorded version number.

The term *consensus review* refers here to an assisted criticism and revision
procedure. Agreement is not proof of correctness, a novelty certificate,
expert peer review, or experimental validation. Resolve comments against the
sources and observed checks; retain unresolved disagreement.

## Match validation to the claim

Different checks address different possible errors. The planned evidence for a
claim should identify what each check establishes and what remains open.

| Check | Purpose and boundary |
|---|---|
| Primary-source and expert review | Check attribution, assumptions, interpretation, and the relation to prior work. Preserve inaccessible-source limits and unresolved expert questions. |
| Formal mathematics | Check stated propositions under recorded assumptions and axiom dependencies. Map each formal statement to the intended manuscript claim. A proof does not by itself certify the numerical implementation. |
| Numerical checks | Compare small cases with known answers or an independently written calculation. Where applicable, check sensitivity to numerical resolution and precision. These are planned checks until executed. |
| Software checks | Test the implemented data roles, invariants, metrics, failure behavior, and interfaces. Synthetic inputs establish tested behavior rather than measured detection performance. |
| Controlled experiments | Preserve separate fitting, tuning, calibration, and evaluation roles; use justified comparators and uncertainty units. Completed engineering checks do not substitute for the planned scientific comparison. |
| Independent reproduction | Ask another person to rerun a frozen commit and configuration with the recorded input manifests. Reproduction remains pending until the run and its differences are recorded. |

Lean checks a formal statement using its proof-checking machinery; the statement,
assumptions, and source mapping still determine the scientific scope. The
[Lean reference](https://lean-lang.org/doc/reference/latest/Introduction/) describes
its small logical kernel. The project’s [formal verification record](lean-verification.json)
identifies the existing checked statements and explicitly excludes numerical
stability, implementation, convergence, privacy, detection, and runtime claims.
This document adds no new proof or experiment.

These layers are project recommendations. They follow the distinction between
controlled inference and evidence from other contexts discussed in Leedy and
Ormrod’s *Practical Research*, 11th edition, Chapter 4, pp. 105–106. The book is
not a source for current generative-AI policy.
