# Critical literature review workflow

This workflow records what a source supports, what remains uncertain, and how it
changes a research decision. It combines source appraisal with a targeted search
for work that could weaken or replace a proposed contribution. It is a project
procedure, not a claim that every relevant source has been found.

## Read and record each source

Identify the source version before reading. Record the DOI or stable primary
URL, publication and version dates, and a SHA-256 hash when a local file is
available. A hash identifies the file reviewed; it does not establish the
correctness of its content.

Read the substantive methods, assumptions, data description, results, and
limitations. Record page ranges and sections actually read, including the scope
of appendices, proofs, tables, and figures. If extraction loses an equation or
visual, inspect the original page when available. Otherwise retain the limitation
and avoid claims that depend on the unread content. Abstract-only screening,
selected-section reading, full main-text appraisal, and replication are distinct
activities.

Use the following fields for each appraisal. Missing information remains marked
as not reported, unavailable, or unread, according to the actual limitation.

| Field | Record |
|---|---|
| Identity and version | Title, authors, DOI or primary URL, version date, file hash, and acquisition status. |
| Reading scope | Exact pages and sections read; appendix, proof, reference, and visual coverage; unread material. |
| Purpose and method | Research question, component roles, architecture, local update, aggregation, and relevant assumptions. |
| Data and access | Native observation units, provenance, labels, participant construction, preprocessing, and information available at each stage. |
| Evaluation design | Fitting, tuning, calibration, and test roles; baselines; tuning budgets; repetitions; uncertainty calculation. |
| Reported claims | Findings with page, equation, table, or figure locations. Mark them as author-reported unless independently reproduced. |
| Strengths and limits | Useful evidence, author-declared limitations, and separately labeled reviewer inferences. |
| Research role | Whether the source supplies a method, dataset, baseline, theoretical condition, deployment constraint, or counterexample. |
| Close precedents | Work that already answers, narrows, or contradicts the proposed question; exact similarities and differences. |
| Follow-up checks | Unresolved passages, missing artifacts, targeted search terms, and the check that could change the appraisal. |

Keep a short readable summary alongside the detailed record. The summary should
state the method and data, the strongest relevant validity limit, and the source’s
role in the research argument. Save the record after each source so that coverage
can be audited without reconstructing reading history.

## Reconcile newly supplied files

Before counting a new PDF as a new work, compare its DOI or stable primary
identity, title, authors, and version with the retained register. A supplied batch
may contain works already appraised. Record supplied-file counts separately from
new retained works, and preserve which files matched which records.

A SHA-256 hash identifies file bytes, not a unique research contribution.
Different files may be versions of the same work. Keep a version-specific reading
record when the content changes, and do not count a duplicate file as a new
appraisal. Verify citation metadata before adding the distinct work to the
bibliography. Do not infer the first-online date from a PDF's modification date
or from a future issue year alone.

## Connect evidence tables to their source records

Keep comparison tables native and editable, with a stable source identifier for
each row. Record a method’s objective, actual data, evaluation conditions and
relevant limitation before comparing it with another study. A compact cell does
not replace its detailed appraisal or extend its reading scope. Separate an
author-reported result from a reviewer’s inference, and retain contradictory
evidence instead of forcing every source to support the proposed contribution.

The current retained catalog contains 87 works. Its source map is distinct from
the working Zotero collection, which has 87 verified parent records. The
manuscript bibliography contains 89 entries because it also includes two software
sources. A bibliography entry, an in-text citation, a retained source and an
appraised main text are different counting units. Chapter 3 currently cites
59 works.

The 16 additions comprise 13 substantive PDF main-text appraisals and three
limited records. Their individual page, appendix and visual limits remain in the
private register. Counts describe recorded work; they do not reconstruct a
systematic-review screening denominator. Similarly, a chart of bibliographic
issue years describes this selected collection rather than field-wide publication
growth. Preserve a verified first-online qualification when an issue year is
later than the collection date.

The reusable [figure and table workflow](figure-workflow.md) keeps production
checks separate from source appraisal. Public documentation describes that
process without exposing the private comparison matrix, chapters or article
files.

## Keep source units separate from repeated runs

Record separately the independently acquired sources, the observations derived
from each source, and the repeated model fits. A different random seed produces
another fit on the stated data; it does not acquire another capture, site, or
population. If source independence is unresolved, preserve that uncertainty even
when the number of records or fits is large.

For each summary or uncertainty interval, state what varies. Possible units
include acquisition source, participant, episode, data split, and initialization.
Do not silently replace one unit with another. The primary
[NeurIPS checklist guidance on experimental uncertainty](https://neurips.cc/public/guides/PaperChecklist)
asks authors to identify the factors represented by their error bars and explain
their calculation and assumptions. Use that distinction when reading a paper
and when designing a later experiment.

## Synthesize and challenge the proposed contribution

Group evidence by the research question and the conditions under which results
were obtained. Compare methods on shared dimensions before interpreting their
reported performance. A higher score on a different dataset does not supply a
controlled comparison between methods.

For each candidate gap, retain a compact decision record.

1. State the question and its intended scope without claiming priority.
2. Identify the closest precedent and explain what it already answers.
3. Name the remaining difference in data, information access, intervention,
   assumptions, evaluation, or operating conditions.
4. Search specifically for a precedent that removes that difference. Record
   search terms, dates, sources checked, and access limits.
5. State a plausible null or adverse result and the observation that would
   weaken the proposed explanation or make the proposed method unnecessary.
6. Decide whether to retain, narrow, defer, or reject the question. Preserve
   material uncertainty and the condition for reconsidering the decision.

An author’s future-work statement is a lead to investigate, not sufficient
evidence of a current gap. Likewise, failing to find a precedent in a bounded
search does not establish that a question is the first of its kind. Keep the
search boundary beside any novelty claim.

## Use independent critique as guidance

Give reviewers a bounded evidence packet and record its version or hash, the
reviewer’s reported model or identity, access scope, completion status, and
substantive disagreements. Distinguish a packet-only critique from a review that
could inspect source material or execute code. If the resolved model or a timing
field is not reported, leave it unreported.

Check reviewer recommendations against primary sources and observed evidence.
Record corrections and reasons for accepting or rejecting advice. Agreement
among reviewers does not prove a claim, validate an experiment, or certify
novelty. Sources added after a review must not be attributed to that review’s
evidence.

Publish reusable procedures and checked summaries. Keep private drafts, raw data,
article PDFs, correspondence, credentials, and private reviewer packets outside
the public repository. The [project status](project-status.md) records which
research and engineering activities have actually been completed.
