# Project status

Updated November 2, 2026.

This repository provides the code and documentation used to prepare the study.
The [Research hub](https://oliabak.com/research/federated-ddos/) is the continuing
project index. The thesis is being drafted and revised in English, with French
translation and proofreading planned after the English manuscript is complete.

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

1. Establish eligible source units, capture and ownership provenance, available
   benign history, and fitting, calibration, and evaluation roles. The final
   evaluation split remains unresolved.
2. Freeze a bounded comparison protocol with explicit information access,
   preprocessing, tuning budgets, uncertainty analysis, and failure accounting
   before interpreting the main experiments.
3. Run the selected federated-learning comparisons and preserve exact code,
   configuration, source hashes, timing boundaries, and unsuccessful attempts.
4. Specify and verify any Sellier-inspired training treatment before comparing
   it with SGD and Adam. No QiML numerical engine is currently claimed.
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
