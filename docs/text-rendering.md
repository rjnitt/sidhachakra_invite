# Phase 2 Text Rendering

Status: implementation, automated checks, and refreshed visual samples approved on 2026-10-21.

Updated 2026-10-21: the user approved fixed 16 pt consecutive-row placement,
manual correction of long entries, and a small text-area adjustment. These updates
supersede the original PRD's automatic shrinking/wrapping and vertical group centering.

## Engine

The independent `TextLayoutService` uses PyMuPDF Story's HarfBuzz-backed HTML text
shaping. It does not rely on simple PDF `insert_text()` calls or system fonts.
The bundled Noto Sans Devanagari font covers the tested Hindi, Latin, digits, and
punctuation. Unsupported glyphs are rejected rather than silently replaced.

The service takes an immutable `RecipientText` and the calibrated layout. It:

1. Preserves each original string without normalization, honorifics, translation,
   truncation, or spelling changes. Whitespace-only optional values create no line.
2. Escapes input as literal text before shaping.
3. Shapes and measures actual embedded-font vector glyph bounds.
4. Uses exactly 16 pt for every populated field, without reduction or wrapping.
5. Removes whitespace-only optional fields before assigning consecutive writing rows.
6. Centers each line horizontally, starting on the first available writing row.
7. Uses a fixed 32.64 pt row pitch to avoid the immutable printed writing rules.
8. Returns a clear manual-correction error if text cannot fit at 16 pt.

Each field is limited to 500 characters. Embedded controls and line separators
are rejected; Devanagari ZWJ/ZWNJ shaping characters are allowed. The limits here
belong to the service; request-validation APIs will be implemented in later phases.

## Output

`fit()` returns the original input, chosen shared size, positioned shaped lines,
and warnings. `overlay_pdf()` produces an independent transparent text-only vector
PDF, with the used font glyphs embedded. `overlay_png()` rasterizes only that text
overlay for visual review, with alpha transparency at four-times scale by default.

These methods do not load or modify the invitation template. The fixed-data review
helper layers the text over a separately rendered source crop in an HTML gallery.
Phase 3 subsequently added complete four-page PDF proofs for the same fixed examples;
see [pdf-generation.md](pdf-generation.md). Runtime generation remains memory-only.

## Original-artwork constraints

The updated rectangle is x 202, y 614, width 235, height 90 PDF points.
The user approved this recalibration on 2026-10-21 to accommodate fixed 16 pt text.
Measured horizontal rule bands, with a small safety allowance, are:

| Rule | Excluded page-y range (pt) |
| --- | --- |
| First | 638.7 to 642.0 |
| Second | 671.3 to 674.7 |
| Third | 704.0 to 706.3 |

Optional empty fields do not generate text or reserve a writing row. Name is row 1;
Second Line is row 2 if populated, followed by City. If Second Line is empty, City
uses row 2. If both optional fields are empty, only the complete Name appears.
This is identical for Hindi and English. Strict group centering and the previous
wide two-field spacing have been removed with explicit user approval. No artwork
is erased, and the original labels and rules remain intact.

## Warnings and errors

Successful layouts have no fitting warnings because font size and row pitch are fixed.
Previous reduction, wrapping, minimum-size, and spacing-adjustment warnings are no
longer generated. Long entries return a manual-correction error instead of changing
their text or typography.

Excessive length, unsupported characters, missing font assets, and unsafe overflow
raise `LayoutError` with messages that do not include recipient strings. Later
batch handling must record a failed row and continue unrelated records.

## Unicode extraction limitation

HarfBuzz produces visually shaped Devanagari ligatures and embedded vector glyphs.
Some ligatures have imperfect PDF text-copy/extraction mappings in this renderer.
The original Unicode strings remain unchanged in the in-memory layout result,
but exact searchable/copyable Hindi cannot currently be guaranteed. Do not use PDF
text extraction alone as evidence of a changed visible name. This limitation is
disclosed rather than claiming full Unicode searchability; no raster fallback is
needed for the tested visual rendering.

## Font provenance and license

- Source: Google Fonts, `ofl/notosansdevanagari/NotoSansDevanagari[wdth,wght].ttf`.
- Downloaded 2026-10-20 from the official `google/fonts` GitHub repository.
- Local asset: `assets/fonts/NotoSansDevanagari.ttf`.
- SHA-256: `14ec4af41f27482216d1c2229f417ff9b1425e1babb014e57d1d40d03229853e`.
- SIL Open Font License 1.1 is bundled unchanged in `assets/fonts/OFL.txt`.
- Runtime shaping is offline; no font CDN or third-party API is used.

PyMuPDF's own AGPL/commercial licensing remains a separate deployment review item.

## Verification and review

Run `python -m pytest -q`: 51 tests passed locally on Python 3.12/macOS.
Layout coverage includes required matras/conjunct strings, Hindi/English/mixed
names, manual correction for long fields, fixed 16 pt, consecutive optional fields, horizontal centering,
embedded fonts, exact maroon color, input escaping, overflow rejection, transparent
edges, and zero personalized ink within the writing-rule bands.

Generate fixed public examples with `python -m tests.render_layout_samples`.
Open [the sample gallery](../tests/artifacts/layout/index.html) directly in a browser.
The helper accepts no user uploads; its persisted development artifacts contain
only fixed PRD examples. Production recipient-data persistence is not introduced.

Desktop and mobile screenshot/layout checks passed at 1440 px and 390 px. Please
review the full Phase 3 PDF proofs before authorizing Phase 4.
Linux/Render verification remains Phase 8 work. Existing non-failing PyMuPDF SWIG
and Starlette/AnyIO deprecation warnings remain documented.