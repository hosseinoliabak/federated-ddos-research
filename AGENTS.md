# Research repository instructions

Keep scientific claims tied to the implemented procedure and available evidence. Mark synthetic fixtures, engineering checks, exploratory analysis, and confirmatory results distinctly. Do not invent findings or infer a working QiML engine from the presence of formal algebra checks.

Keep code in this repository and runtime data under `FDDOS_WORKSPACE`. Preserve original datasets and completed runs. Do not commit credentials, datasets, model files, article PDFs, private drafts, or correspondence. Do not replace source-client ownership or labels silently.

Use the locked environment and run the unit checks, engineering self-test, and synthetic integration workflow after code changes. Add a targeted regression test for defects affecting scientific validity. Changes to data roles, features, local updates, aggregation, or metrics require a new documented experiment version.

The current final evaluation split and QiML numerical specification are unresolved. Preserve reserved test sources outside development. Before changing Lean claims, check the mapping between the source, assumptions, and formal statement; a successful build alone does not verify that mapping.

Use simple English. Document component purpose before implementation details. Keep setup instructions runnable from a clean checkout and identify the scope of every test or result.

## Thesis code references

When a thesis method, algorithm, formal statement, figure, table, or reported result depends on this project, reference the relevant source file and function or theorem where useful. Use a GitHub permalink containing the full commit SHA, with line anchors when they help the reader. Verify the linked implementation before citing it; a branch URL is not an exact version reference.

Associate each reported result with the code version actually executed, run identifier, configuration, dependency lock, and artifact record. Historical runs made before this repository must retain their original source hashes; do not attribute them to a later portable version. Add an APA 6 software reference based on verified metadata when the manuscript cites the project, and continue to cite the original methodological papers separately. Keep a concise chapter-to-code mapping as the manuscript develops. Code links document implementation and do not by themselves establish scientific validity.
