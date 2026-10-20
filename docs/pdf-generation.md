# Phase 3 PDF Generation

Date: 2026-10-21. Phase 2 samples and Phase 3 execution were approved by the user.
The Phase 3 generation engine and automated acceptance checks are complete.
Phase 4 was subsequently approved and implemented; see [single-api.md](single-api.md).

## Composition

`generate_invitation()` accepts an immutable loaded template, calibrated layout,
and recipient text. It verifies the source fingerprint, page count, dimensions,
and rotation, then uses the approved fixed-16-point text layout service.

The function opens a fresh in-memory copy of the original four-page PDF and
imports the transparent vector text overlay onto Page 1 only. It exports to bytes
without reconstructing or rasterizing the invitation pages, resizing pages, or
recompressing the original image streams. The result is reopened to check page
count, media boxes, crop boxes, and rotation before being returned.

The original template is never opened for writing. A failed layout returns the
existing manual-correction error without producing an invitation or reserving a
filename. No honorific, surname, translation, normalization, or truncation is
applied to the visible recipient text.

The returned immutable `GeneratedInvitation` contains:

- `data`: complete four-page PDF bytes, excluded from its diagnostic representation.
- `filename`: a filesystem-safe download filename.
- `warnings`: the text layout warnings; fixed-size successful examples have none.

## Filenames

The visible input is independent of filename sanitization. Unicode Hindi and
English are retained where safe. Whitespace becomes underscores; path separators,
unsafe filename characters, and control/format characters are replaced. Empty
sanitized names use `Recipient`. The fixed `Invitation_` prefix also avoids reserved
Windows device basenames such as `CON`.

Filenames are capped at 240 UTF-8 bytes without splitting an encoded character.
Only filenames are shortened, never the text printed on the invitation.

A caller-owned, request-local `used_filenames` set produces:

````text
Invitation_Rohit_Jain.pdf
Invitation_Rohit_Jain_2.pdf
Invitation_Rohit_Jain_3.pdf
````

Collision comparison accounts for case and canonically equivalent Unicode spelling
to avoid overwrites after extraction on common filesystems. Natural suffixes and
long names that truncate to the same stem are checked against the same set.
No global filename registry, database, persistent job, or recipient history is created.

## Review proofs

Open the [fixed-data sample gallery](../tests/artifacts/layout/index.html) and choose
**Four-page invitation PDF** under an example. The HTML download attribute supplies
the service-generated Unicode filename. This local development gallery is not
evidence of production or mobile-browser download compatibility; that comes later.

- [Hindi three-field invitation](../tests/artifacts/layout/sample-1-invitation.pdf).
- [Hindi name and city](../tests/artifacts/layout/sample-2-invitation.pdf).
- [English name only](../tests/artifacts/layout/sample-3-invitation.pdf).
- [Mixed Hindi and English](../tests/artifacts/layout/sample-4-invitation.pdf).
- [Hindi matras and conjuncts](../tests/artifacts/layout/sample-5-invitation.pdf).
- [English name and city](../tests/artifacts/layout/sample-6-invitation.pdf).
- [Actual generated first-page render](../tests/artifacts/layout/first-generated-page.png).

Regenerate these fixed development artifacts with:

````bash
source .venv/bin/activate
python -m tests.render_layout_samples
````

The helper saves only public fixed PRD examples. The runtime generator never saves
recipient uploads or output files, and tests verify generation creates no files.

## Verification

`python -m pytest -q`: **69 passed**, including **25 PDF tests**.
`python -m pip check`: no broken requirements.

- Every generated proof contains exactly four pages, approximately 950–986 KB.
- Individual page dimensions, media/crop boxes, and rotations are preserved.
- Original embedded image-stream bytes are unchanged on all four pages.
- Pages 2–4 render identically to the source at 1.5-times scale.
- At twice scale, Page 1 changes only inside the approved recipient rectangle,
  allowing one pixel around the measured rectangle for raster-boundary rounding.
- Final text is 16 pt maroon with embedded fonts, not a full-page raster overlay.
- Unicode filename safety, duplicate handling, bounded length, normalized/casefold
  collisions, repeated-request isolation, and failure behavior are covered.
- Source SHA-256 remains `365791e39f67966034ad36df5ecc14d6af1d50405ba47c968e1f7e0fe494548f`.
- First-page render visually reviewed; desktop/mobile gallery assets and links checked.

## Remaining Boundaries

The known Hindi ligature copy/extraction limitation is unchanged; visual vector
rendering and the original in-memory recipient strings are preserved. See the
[text-rendering report](text-rendering.md) for details.

Phase 3 introduced no API generation route. Phase 4 now exposes the single-generation
download API. The production mobile frontend, Excel processing, ZIP packaging,
and Render deployment remain outside these phases. No new infrastructure or dependencies were added.
Existing PyMuPDF SWIG and Starlette/AnyIO deprecation warnings are non-failing.
Linux rendering, production licensing/security review, mobile downloads, and
performance targets remain unverified until their planned phases.

The user approved these complete PDFs and Phase 4 execution on 2026-10-21.
Phase 5 still requires explicit approval.