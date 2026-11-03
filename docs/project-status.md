# Project status

Updated November 3, 2026.

This repository provides the code and documentation used to prepare the study.
The [Research hub](https://oliabak.com/research/federated-ddos/) is the continuing
project index. The thesis is being drafted and revised in English, with French
translation and proofreading planned after the English manuscript is complete.

Human review now uses private Word copies with tracked changes and comments.
The [Word review workflow](word-review-workflow.md) records how edits are
preserved, reconciled with the canonical source, and checked before a new export.

## Current preparation checkpoint

The research questions have been reopened after a fresh critical appraisal of
the literature. A direction has now been selected for feasibility assessment;
the final questions and protocol remain under review. The retained register
contains 84 sources: 71 original sources
and 13 additional sources. All 71 original sources have fresh substantive
appraisals. Of the additional sources, ten have primary PDFs and full substantive
main-text appraisals. The other three have explicitly limited coverage: metadata
and abstract, selected primary sections, or extracted main prose with image-only
tables and plots still unread. These coverage categories remain separate.

The [critical literature review workflow](critical-literature-review.md) records
how source versions, exact reading scope, reported claims, validity limits, and
close precedents are checked. Completed reading does not establish replication,
novelty, or an accepted research protocol. Later source additions also remain
outside the evidence supplied in earlier independent-review packets.

The updated abstract and chapter text record this feasibility stage. The final
problem statement, contribution claims, data eligibility, and comparison
protocol remain subject to review. Earlier chapter checks and
completed engineering work remain historical evidence; they do not settle the
revised scope or establish manuscript readiness.

Independent reviews provide critiques of bounded evidence and proposed decisions.
Their access scope, disagreements, and resulting corrections are recorded
separately from historical software reviews. Reviewer agreement is not proof of
correctness or novelty.

This checkpoint adds literature appraisal and documentation. It adds no new
training run, final-test result, accepted final split, or numerical QiML engine.
The next research step is to resolve the scope and data requirements, then freeze
a bounded protocol before the main comparisons.

## Verified engineering work

The published benign-only pilot source is
[version 2 at commit 102293e](https://github.com/hosseinoliabak/federated-ddos-research/tree/102293e69f2f9e7cdcac58cb12ffe8d7d0165833).
Its recorded checks comprise 43 unit tests, the engineering self-test, and the
synthetic integration workflow. The associated
[GitHub Actions job](https://github.com/hosseinoliabak/federated-ddos-research/actions/runs/41377919244/job/125062143656)
passed. The [pilot guide](benign-engineering-pilot.md) describes its input checks,
data roles, controls, failure records, and known limits.

The completed historical version 1 run retains its original code and artifact
provenance. Version 2 has not been rerun on the real development sample, and its
changed shuffle seeds must not inherit version 1 measurements. This documentation
checkpoint adds no new training run or experimental result.

The dataset diagnostics, engineering checks, and scoped Lean statements support
specific preparation tasks. They do not establish a scientific comparison,
independent-source generalization, an optimizer speedup, or deployment readiness.
See the [methodology](methodology.md), [feature-validity procedure](feature-validity.md),
and [formal verification record](lean-verification.json) for their respective scopes.

## Remaining research gates

1. Resolve the research questions and contribution claims against the strongest
   relevant prior work. Revise the abstract and affected chapters consistently.
2. Establish eligible data, capture and ownership provenance, and fitting,
   calibration, and evaluation roles. The final evaluation split remains
   unresolved.
3. Freeze a bounded comparison protocol with explicit information access,
   preprocessing, tuning budgets, uncertainty units, and failure accounting
   before interpreting the main experiments.
4. Run the selected comparisons and preserve exact code, configuration, source
   hashes, timing boundaries, and unsuccessful attempts. Specify and verify any
   Sellier-inspired training treatment before comparing it with SGD and Adam.
   No QiML numerical engine is currently claimed.
5. Validate the [portable model interface](portable-models.md) and network-lab
   capture path before making claims about live detection. A CSV experiment and
   a network deployment require different supporting evidence.

## Publication and version records

Public updates contain reusable code, checked documentation, and bounded project
status. Private manuscript files, raw datasets, trained models, correspondence,
and private tracking records remain outside this repository. The Research hub
links the public records.

At the end of a substantive task or workday, check whether code, documentation,
or project status changed and publish the relevant checked update. A checkpoint
without a code change should report that fact rather than create an empty code
release. Keep historical results tied to the version actually executed, even
after newer documentation is published.
