# Original PDF Inspection and Draft Calibration

Date: 2026-10-20. Phase 1 status: **complete; user approved placement on 2026-10-20**.

## Source integrity

The uploaded original was copied without alteration from `assets/fonts/invitation.pdf`
to the PRD's expected path, `assets/invitation.pdf`. Both retain this SHA-256:

````text
365791e39f67966034ad36df5ecc14d6af1d50405ba47c968e1f7e0fe494548f
````

All inspection uses a read-only byte snapshot. Preview rendering does not save or
rewrite the PDF. No source page has been reconstructed or rasterized for output.

## Measured pages

Coordinates are PDF points, with 72 points per inch. All pages have zero rotation,
and each crop box equals its media box.

| Page | Width (pt) | Height (pt) | Rotation | Extractable text characters | Images |
| --- | --- | --- | --- | --- | --- |
| 1 | 647.03 | 908.05 | 0 | 0 | 1 |
| 2 | 614.03 | 907.05 | 0 | 0 | 1 |
| 3 | 614.03 | 907.05 | 0 | 0 | 1 |
| 4 | 624.03 | 907.05 | 0 | 0 | 1 |

These are not four identically sized pages. Future output must retain every page's
individual dimensions. The source is image-based, so its existing wording is not
searchable text. This does not justify rasterizing or re-encoding the final pages.

Exact numeric metadata is in [template-inspection.json](../config/template-inspection.json).

## First-page preview

PyMuPDF renders Page 1 at a scale of 1.5 to a 971 x 1363 PNG. The application caches
the original preview in memory at startup; no recipient information is involved.
The saved review artifact is [template-preview.png](../assets/template-preview.png).

## Initial recipient rectangle

Historical Phase 1 calibration is recorded below. On 2026-10-21, the user approved
fixed 16 pt consecutive-row placement and adjusted the rectangle to x 202, y 614,
width 235, height 90 pt. See [text-rendering.md](text-rendering.md) for current behavior.

The original lower recipient panel and its printed labels were visually inspected
in the rendered preview. A conservative rectangle to the right of the label is
proposed, inside the existing panel:

| Property | Draft value |
| --- | --- |
| Page | 1 |
| Origin | Top left |
| x | 202 pt |
| y | 620 pt |
| Width | 235 pt |
| Height | 85 pt |
| Right edge | 437 pt |
| Bottom edge | 705 pt |
| Alignment | Horizontal and group-vertical center |
| Color | #800020 |
| Initial shared font size | 12 pt |
| Minimum shared font size | 8 pt |
| Initial line-height multiplier | 2.7 |
| Intended font | Noto Sans Devanagari, bundled in Phase 2 |

The rectangle is user-approved; typography values remain provisional. The line-height multiplier is
deliberately generous because the artwork already includes writing rules. Phase 2
must verify actual shaped glyph extents, optional-line centering, and collisions
with those rules. Font reduction or wrapping must not silently cross artwork;
if safe fitting is impossible, return a layout error rather than erase the rules.

The fixed labels, including the preprinted honorific, remain part of the original
artwork. No extra honorific will be inserted or removed programmatically. Entered
recipient text will not be altered to compensate for the printed label.

## Coordinate mapping

For page width W and height H, the browser rectangle is `(x/W, y/H, width/W, height/H)`.
The backend returns these normalized values and the original PDF-point rectangle.
Desktop and mobile browser checks verify the outline against the API to within
0.0001 normalized units. Image raster rounding is less than one preview pixel.

The configuration is bound to the source SHA-256. A different PDF or changed
dimensions requires inspection and recalibration, not silent reuse of these bounds.

## Review and limitations

Open `http://127.0.0.1:8000/api/template/calibration` to review the green outline.
This is a read-only calibration view, not the Phase 5 personalization interface.
No recipient samples or personalized PDFs are generated in Phase 1.

- 21 API and PDF tests passed; dependency checks passed.
- Source hashes remained unchanged after tests.
- Desktop and mobile screenshots, outline mapping, and visibility toggle checked.
- User approved the outlined rectangle on 2026-10-20; Phase 1 is complete.
- Phase 2 shaping and fitting results are recorded in [text-rendering.md](text-rendering.md).
- Linux deployment remains unverified.
- PyMuPDF licensing obligations must be reviewed before public deployment.

Phase 2 execution was subsequently approved. Phase 3 still requires explicit approval.