# Contributing

Use an issue or pull request to explain the problem, the proposed change, and the evidence needed to assess it. Describe changes to scientific assumptions separately from code fixes. A result that changes after an algorithm or split change is a new experiment, not a silent correction to an old log.

Run the unit checks and synthetic integration workflow before submitting a change. Add a focused regression case for a defect that could affect grouping, data roles, aggregation, labels, metrics, or retained records. Keep examples small enough to run without restricted datasets.

Keep code, configurations, documentation, and validation evidence together. Record dependencies in `pyproject.toml` and update `uv.lock` deliberately. Preserve existing run directories and use a new version for a changed protocol. Do not run Python with `-O`, because checked assertions are part of this prototype's preconditions.

Do not commit raw datasets, packet captures, private reports, article PDFs, credentials, tokens, emails, or model checkpoints. Generated examples should be clearly synthetic. Git ignore rules reduce accidental additions; review the staged file list before pushing.

The original scripts are research prototypes. Contribution review should assess both software behavior and the meaning of the experimental claim. A passing test or Lean build does not establish the validity of a new scientific interpretation.

Contributions are accepted under the repository's MIT license. Authors retain credit for their contributions. Source methods and datasets need their own citations, and their licenses remain separate.
