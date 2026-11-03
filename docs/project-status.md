# Project status

Updated November 3, 2026.

This repository provides the code and documentation used to prepare the study.
The [Research hub](https://oliabak.com/research/federated-ddos/) is the continuing
project index. The thesis is being drafted and revised in English, with French
translation and proofreading planned after the English manuscript is complete.

Human review of Chapter 1 remains pending. Private review material and the
researcher’s comments remain outside the public repository.

## Current preparation checkpoint

The nine-chapter English working draft has been revised throughout around the
current working study direction. Its four research questions have distinct roles,
with the primary comparison separated from supporting and conditional work.
Required source data, study feasibility, and the final protocol remain to be
checked. Human review of Chapter 1 is still pending.

The retained working collection now contains 87 verified parent records.
Newly supplied files were reconciled with existing records before three new works
were added. All 71 original sources have fresh substantive appraisals; additional
works retain their individually recorded reading coverage and limits. A retained
record is not automatically a full main-text appraisal, and reading is not
independent replication.

The [critical literature review workflow](critical-literature-review.md) records
source identity and versions, duplicate-file reconciliation, exact reading scope,
reported claims, validity limits, and close precedents. Later source additions
remain outside the evidence supplied in earlier independent-review packets.

The abstract and chapter text retain the prospective status of the study.
Earlier chapter checks and engineering work remain historical evidence; they do
not establish the revised protocol, empirical findings, or manuscript readiness.
Novelty remains provisional and must be assessed against the strongest relevant
prior work.

Independent reviews critique bounded evidence and proposed decisions. Their
access scope, disagreements, and resulting corrections are recorded separately
from historical software reviews. Reviewer agreement does not prove correctness,
certify novelty, or replace human review.

This checkpoint adds source appraisal and manuscript/documentation realignment.
It adds no new training run, final-test result, accepted final split, or numerical
QiML engine. The next steps are Chapter 1 review and source-data feasibility
checks before the bounded protocol is frozen and the main comparisons begin.

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

1. Complete human review of Chapter 1 and reconcile its comments. Keep the
   working questions, contribution limits, and affected chapters consistent with
   the strongest relevant prior work.
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
