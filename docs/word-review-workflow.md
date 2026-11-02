# Word review workflow

Word documents are the preferred format for human review of the working
manuscript. The manuscript and edited review copies remain private. This
repository documents the workflow without publishing those files.

## Review and reconcile

1. Export a review copy from the checked canonical source and record its source
   revision. Keep the exported original for comparison.
2. Review in Word with Track Changes and comments. Save the edited copy before
   sharing it for reconciliation.
3. Inspect the returned changes and comments. Accept or reject each substantive
   change against the sources, equations, and intended meaning.
4. Merge accepted corrections into the canonical manuscript source and citation
   records, then check the affected content before generating the next review
   copy. Preserve the earlier review record.

Check whether a review file has changed before refreshing an export. An edited
copy must be preserved and reconciled; it must not be replaced automatically by
a new export. Keep unresolved comments visible until their disposition is
recorded.

## Export details and limits

The current export uses editable Word equations in OMML format, consistent with
the [Pandoc DOCX math output](https://pandoc.org/MANUAL.html#math). Tables,
figures, equations, and cross-references still require inspection after
conversion. Word pagination can differ from the typeset PDF, so identify review
comments by chapter, section, and nearby text rather than relying only on a page
number.

Current citations and bibliography entries are APA 6 formatted text. They are
not live Zotero fields. Reconcile accepted citation changes with the canonical
reference records before the next export.

When reading a reviewed DOCX with conversion software, preserve its revision and
comment information deliberately. Pandoc's default DOCX reader accepts tracked
insertions and deletions and omits comments; its
[`--track-changes=all` option](https://pandoc.org/MANUAL.html#option--track-changes)
retains those records for inspection. Conversion is not a substitute for deciding
which proposed changes to accept.
