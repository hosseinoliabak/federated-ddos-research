# Figure and table workflow

Keep the evidence, editable source and exported display separate. An explanatory
figure can clarify component roles or information flow without reporting a
measured result. Its caption should state that role and any limitation needed to
interpret it. A table that summarizes source evidence should retain each study’s
conditions and reading limits.

## Prepare and preserve the source

Start with a claim and source record. Decide which relationships need a drawing
and which facts belong in a native table. Use original geometry and wording
rather than copying a published figure. Attribute source concepts in the
manuscript and record the location actually consulted. Do not add illustrative
numbers, selected architectures or measured-performance implications without
evidence.

The checked local route uses Diagrams for editable draw.io drawings and
Matplotlib for a descriptive chart. Keep the drawing or plotting code, its input
metadata and an output manifest together. A manifest should identify the source
version, output hashes, tool versions, caption and the checks actually completed.
Keep earlier versions when labels, geometry or source evidence change.

## Produce the required formats

Export the drawing to native-text SVG, vector PDF and PNG from the same source.
Native text keeps labels inspectable, although font availability can still affect
an SVG’s appearance. The checked PDF exports contain vector objects and embedded
font subsets. PNG remains a fallback and preview rather than the canonical
editable source. For a chart, preserve the code and metadata that generated its
labels and values.

The current private workflows use different formats for different destinations.
The offline LaTeX build accepts the actual vector PDF. The checked Word route
stores actual SVG with a PNG fallback. The browser manuscript workspace currently
uses a text-only LaTeX vector companion generated from the same geometry. That
companion is a separate rendering of the shared drawing description; it is not
an import of the SVG bytes. The routes can differ in font metrics and arrowhead
outlines, so identical source relationships do not establish pixel-identical
output.

Keep the canonical caption in manuscript text. Use one figure identifier for its
references, caption and associated assets. A native Word table preserves editable
cells. An inserted SVG is a vector picture, not editable Word diagram shapes;
the draw.io file remains the drawing’s editable source.

## Check structure and appearance

Before integration, check that all intended labels and connections are present.
Inspect the SVG for native text and unintended active or external content, and
check the PDF for the expected fonts and raster-image objects. For Word, verify
the SVG and fallback relationships, content types and media hashes. These checks
establish file structure and source correspondence, not final page fit.

Inspect the actual destination rendering at its intended size. Check line
routing, label size, clipping, contrast, captions and reference numbering. Inspect
native Word when available and retain any unsuccessful attempt as a limit rather
than treating XML inspection as a native-layout result. A successful generic
fixture does not establish that every final figure or the complete manuscript
has been checked.

Keep private chapters, source evidence matrices and assets outside the public
repository unless they have separate publication authorization. This document
describes a reusable workflow; it does not publish those materials or establish
a new detector, training result, implementation speedup or deployment.
