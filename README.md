# Jain Invitation Personalizer

Source of truth: [`prd.txt`](prd.txt). **Single-invitation Render configuration prepared; public deployment pending. Bulk remains paused.**

User-approved updates on 2026-10-21 override the PRD's automatic fitting and strict
group centering: fixed 16 pt, consecutive writing rows, no shrinking or wrapping.
City becomes the second rendered line when Second Line is empty; without either
optional field, only the full Name is rendered, unchanged.

## Requirements

- Python 3.12 (tested locally with 3.12.14).
- Visual Studio Code with Microsoft's Python extension.
- No database, PDF, fonts, Node.js, or external service is needed for Phase 0.
- Phase 1 requires the bundled original at `assets/invitation.pdf` and matching
	draft calibration in `config/layout.json`. No database or external service is needed.

## Local setup on macOS

````bash
cd invitation_name_in_bulk
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
````

In VS Code, run **Python: Select Interpreter** and choose `.venv/bin/python`.
Run **Python: Configure Tests**, choose **pytest**, and select `tests`.
These steps do not initialize or manage Git.

## Run locally

````bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
````

From a second terminal:

````bash
curl --fail http://127.0.0.1:8000/api/health
````

Expected response:

````json
{"status":"ok","template_loaded":true}
````

Startup now verifies the four-page template and its calibration fingerprint.
Missing, invalid, or changed templates prevent startup. Health reports template
availability, not a full generation/download probe.
Interactive API documentation is available at `http://127.0.0.1:8000/docs`.
Open `http://127.0.0.1:8000/` for the mobile-first personalization frontend.
No frontend installation, build step, external font service, or Node.js runtime is required.

## Single invitation workflow

1. Enter the full Name and, optionally, Second line and City / Location.
2. The full first-page image updates locally as you type; typing sends no recipient requests.
3. Select **Check exact preview** to verify placement with the same renderer used for the PDF.
4. Select **Generate & download PDF**. Form values remain available for corrections.
5. If the browser does not save automatically, use **Download PDF** or **Open PDF in a new tab**.
	On iPhone/iPad, Safari may require **Share > Save to Files**.

The live canvas is an approximate preview. The on-demand PNG is authoritative: its pixels
match Page 1 of the generated PDF for the same input and approved template/configuration.
Any edit removes old exact previews and download links. Results from requests started
before an edit are discarded. Bulk navigation and its client script are disabled while
the app focuses on single invitations. Existing bulk work is retained for later;
resume Phase 6 only after explicit user approval.

Production requests use only memory. Recipient data is not written to local/session storage
or server files. Keep any PDFs you explicitly download in accordance with your own privacy needs.

Optional frontend unit checks use Node.js 22.7+ (no npm packages):

```bash
node --test tests/test_preview.mjs
node --check frontend/js/app.js
```

## Phase 1 calibration review

Open `http://127.0.0.1:8000/api/template/calibration` while the server is running.
The dashed green rectangle is the proposed recipient area, not a modification to
the original image or PDF. Toggle **Recipient area** to compare the unchanged page.

- [Inspection report](docs/pdf-inspection.md).
- [Measured page metadata](config/template-inspection.json).
- [Draft layout](config/layout.json).
- [Original first-page PNG](assets/template-preview.png).
- `GET /api/template/preview`: first-page PNG rendered from the loaded PDF.
- `GET /api/template/layout`: normalized coordinates and draft typography settings.

**Updated placement approved on 2026-10-21:** x 202, y 614, width 235, height 90 PDF points.
Fixed 16 pt text occupies consecutive original writing rows without skipped rows.
Group-vertical centering was replaced with writing-row placement by user approval.
Text that cannot fit at 16 pt requires manual correction; no shrinking or wrapping occurs.

## Text and four-page PDF samples

Open [the fixed-data sample gallery](tests/artifacts/layout/index.html) directly in
your browser. It contains six Hindi/English examples, original-artwork crops,
transparent text overlays, text-only vector PDFs, and complete four-page invitations.
These are development proofs made from fixed PRD examples, not stored user inputs.

Regenerate them from the project root:

````bash
source .venv/bin/activate
python -m tests.render_layout_samples
````

The [text-rendering report](docs/text-rendering.md) covers the shaping engine,
font provenance/license, warnings, rule-aware spacing, and extraction limitations.
The in-memory PDF service is exposed through `POST /api/invitations/single`.

## Phase 3 PDF generation

- [Generation report](docs/pdf-generation.md).
- [Example Hindi four-page PDF](tests/artifacts/layout/sample-1-invitation.pdf).
- [Example English four-page PDF](tests/artifacts/layout/sample-3-invitation.pdf).
- [Rendered generated first page](tests/artifacts/layout/first-generated-page.png).

`generate_invitation(template, configuration, recipient, used_filenames=None)` in
`app/services/pdf_service.py` returns PDF bytes, a safe filename, and warnings.
It composes the existing vector text overlay onto Page 1 of a fresh in-memory copy
of the original template. It never saves the generated invitation to disk.
Pass a request-local filename set when generating multiple recipients to assign
`_2`, `_3`, and later suffixes without overwriting another recipient's name.

The sample helper deliberately saves only fixed development examples. It is not
a production upload or generated-file store. Phase 4 returns PDF bytes directly as a downloadable response.

## Single-generation API

Open `http://127.0.0.1:8000/docs` to try `POST /api/invitations/single`.
The [API contract](docs/single-api.md) documents validation, filenames, and errors.

From a second terminal, download a fixed example to your local temporary folder:

````bash
curl --fail --show-error \
	--request POST http://127.0.0.1:8000/api/invitations/single \
	--header 'Content-Type: application/json' \
	--data '{"name":"Mr. Rohit Jain","second_line":"","city":"New Delhi"}' \
	--output /tmp/Invitation_Rohit_Jain.pdf
````

Name is required. Optional fields may be omitted or empty strings; all fields must
be strings of at most 500 characters. Spelling and whitespace are retained.
Overlong rendered text returns a manual-correction error rather than shrinking,
wrapping, or clipping. The response uses an attachment header with both an ASCII
fallback and a UTF-8 filename, `Cache-Control: no-store`, and `application/pdf`.
The application itself does not save the generated PDF.

No mobile form is implemented yet; the root page still returns HTTP 404.

## Tests

````bash
source .venv/bin/activate
python -m pip check
python -m pytest -q
````

Current automated acceptance criteria:

- Application starts locally and `/api/health` returns HTTP 200.
- Health response contains only availability and template-loaded status.
- Startup requires a valid four-page template and matching, in-bounds calibration.
- Paths work independently of the terminal working directory.
- Unknown routes and direct original-PDF URLs return HTTP 404.
- Cross-origin access is not enabled.
- Dependency consistency checks and automated tests pass.
- PRD and original PDF remain unchanged; only inspection and preview are implemented.
- Normalized preview bounds round-trip to measured PDF-point coordinates.
- Hindi/English shaping uses the bundled font with embedded vector output.
- Populated fields share a size; empty optional fields create no extra text lines.
- All populated fields use 16 pt on consecutive rows; unsafe overflow requests manual correction.
- Transparent-overlay pixel tests verify rule bands and page edges stay blank.

## Project structure

- `app/main.py`: application factory and ASGI entry point.
- `app/api/routes.py`: health, template inspection, exact PNG preview, and single-generation downloads.
- `app/core/config.py`: immutable application metadata.
- `app/models/schemas.py`: validated draft calibration schema.
- `app/services/pdf_service.py`: read-only PDF inspection and preview rendering.
- `app/services/text_layout_service.py`: independent shaping, fitting, and text-only overlays.
- `assets/invitation.pdf`: immutable original template.
- `assets/fonts/NotoSansDevanagari.ttf`, `assets/fonts/OFL.txt`: bundled font and license.
- `config/`: draft calibration and measured inspection metadata.
- `frontend/index.html`, `frontend/css/styles.css`: responsive three-field editor and full-page preview.
- `frontend/js/app.js`, `frontend/js/preview.js`: local overlay, exact verification, and blob downloads.
- `frontend/calibration.html`: Phase 1 read-only calibration view.
- `tests/test_preview.mjs`: dependency-free tests for live-preview rows and PDF-point mapping.
- `tests/test_api.py`, `tests/test_pdf.py`, `tests/test_layout.py`: API, source preservation, and layout tests.

Only direct dependencies are pinned; these files are not a complete transitive
dependency lockfile. PyMuPDF supplies HarfBuzz-based shaping; no additional system
font, paid API, Pillow, or browser runtime is required by the text service.
Excel and upload packages are development-only; bulk endpoints are disabled by default.
Retained bulk tests explicitly opt in using `create_app(enable_bulk=True)`.
PyMuPDF is offered under AGPL/commercial licensing; review applicable licensing
obligations before public deployment.

## Render startup reference

Follow the [personal deployment guide](docs/render-deployment.md). You create and publish
the personal repository; no Git setup or Docker is required. Confirm source/PDF rights
and PyMuPDF licensing before making the application public.

Build:

```bash
pip install -r requirements.txt && python -m scripts.render_check
```

With Render's `PORT` environment variable set, start:

````bash
python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --limit-concurrency 16 --backlog 32 --timeout-keep-alive 5 --no-proxy-headers
````

The [Render Blueprint](render.yaml) declares the Python runtime, free plan, build/start
commands, Python version, and health endpoint. It has no application credentials.
Production dependencies were audited after upgrading vulnerable Starlette/FastAPI pins.
The build check validates the bundled PDF/font and English/Hindi output in memory.
Actual Linux execution and public HTTPS/mobile checks remain pending on Render.

## Phase-completion checklist

- [x] Phase 0 — Project initialization and passing acceptance tests.
- [x] Phase 1 — Inspection, calibration tests, and user placement approval complete.
- [x] Phase 2 — Fixed 16 pt engine tested and refreshed samples approved on 2026-10-21.
- [x] Phase 3 — Four-page generation, safe filenames, and preservation tests passed.
- [x] Phase 4 — Validated single-entry API and downloadable PDF response verified.
- [x] Phase 5 — Mobile frontend, live/exact previews, and single-entry download workflow.
- [ ] Phase 6 — Excel bulk processing.
- [x] Phase 7 — Single-invitation security and reliability; bulk-specific review deferred.
- [ ] Phase 8 — Render deployment.
- [ ] Phase 9 — Final quality assurance.

Phase 1 execution was approved and the original PDF was supplied.
Placement and Phase 2 execution were approved on 2026-10-20.
The user approved Phase 2 samples and Phase 3 execution on 2026-10-21.
The user approved the complete PDFs and Phase 4 execution on 2026-10-21.
The user approved Phase 5 execution after Phase 4 verification.
Bulk development is paused by user request. Obtain explicit approval before resuming
Phase 6 or starting Phase 8 deployment.

## Phase 0 verification — 2026-10-20

- Python 3.12.14 virtual environment created successfully.
- `python -m pip check`: no broken requirements found.
- `python -m pytest -q`: 8 passed in 0.34 seconds.
- Real Uvicorn process started successfully on localhost port 8000.
- HTTP health check returned 200 with `template_loaded: false`.
- No Git initialization, branch changes, worktrees, or deployment performed.

Known limitation: tests emit one dependency deprecation warning from Starlette's
TestClient use of AnyIO's `BlockingPortal` alias. It does not fail the tests;
dependency compatibility and security must be reviewed before deployment.
Render/Linux startup has not yet been tested.

## Phase 1 verification — 2026-10-20

- `python -m pytest tests/test_api.py tests/test_pdf.py -q`: 21 passed.
- `python -m pip check`: no broken requirements found.
- Original and copied template SHA-256 hashes remain identical.
- Desktop (1280 px) and mobile (390 px) browser checks passed: image loading,
  normalized outline mapping, outline toggle, and no horizontal overflow.
- PyMuPDF SWIG and Starlette/AnyIO deprecation warnings remain non-failing.
- User placement approval received on 2026-10-20; coordinates are unchanged.
- Phase 1 did not implement Hindi shaping or PDF generation; Phase 2 progress is recorded below.

## Phase 2 verification — 2026-10-20

- Full suite: 47 tests passed, including 26 text-layout tests.
- Dependency consistency check passed; original PDF hashes remain unchanged.
- Six fixed-data sample galleries rendered successfully with embedded-font vector proofs.
- Desktop (1440 px) and mobile (390 px) screenshots checked: all image assets load,
	no horizontal overflow, transparent overlays stay inside the source-artwork crop.
- Maroon color, common font size, centering, no clipped edge pixels, and no ink in
	measured writing-rule bands checked automatically.
- Empty-name, field-length, control-character, unsupported-glyph, missing-font,
	unbreakable overflow, and invalid rule-band cases tested.
- Original 2026-10-20 samples used adjustable spacing; superseded by the update below.
- Hindi PDF copy/extraction is imperfect for some ligatures; visual vector text
	is preserved, but exact searchable Unicode is not promised.
- Render/Linux verification and final invitation generation remain outstanding.

## Typography update — 2026-10-21

- User requested fixed 16 pt, optional-line collapse, and manual long-text correction.
- User approved consecutive writing rows and modest rectangle recalibration instead
	of strict vertical group centering. Original PDF artwork is unchanged.
- Name is never shortened to its first word. City uses row 2 when Second Line is empty.
- Automatic font reduction, wrapping, and rule-driven row spreading were removed.
- Full test suite: 51 passed, including explicit Hindi/English City-on-row-2 tests.
- Refreshed six-sample gallery and embedded-font proofs are all 16 pt.
- Desktop/mobile screenshots and image-loading/overflow checks passed.
- Original PDF hashes remain unchanged. Phase 3 has not started.

## Phase 3 verification — 2026-10-21

- Full test suite: 69 passed, including 25 PDF tests; dependency consistency passed.
- Six complete sample PDFs generated, each with exactly four pages.
- Each page retains its own original media box, crop box, and rotation.
- Pages 2–4 render pixel-identically to the source at 1.5-times scale.
- Page 1 differs only within the recipient rectangle, checked at twice scale
	with a one-pixel raster-boundary allowance.
- Original embedded image streams and source file SHA-256 remain unchanged.
- Final recipient text retains 16 pt size, maroon color, and embedded fonts.
- Safe Unicode filenames, bounded filename length, duplicate suffixes, case-insensitive
	and Unicode-equivalent collisions, and truncation collisions tested.
- Repeated generation does not leak a previous recipient into later output and
	writes no runtime files. Failed layout does not reserve a filename.
- Complete first-page render visually checked; gallery links and preview assets
	checked on desktop and mobile without horizontal overflow.
- Existing non-failing dependency deprecations and Hindi extraction caveat remain.
- Generation/download APIs, mobile download behavior, and Render/Linux checks remain later-phase work.

## Phase 4 verification — 2026-10-21

- Full suite: 94 tests passed, including 39 API tests; dependency consistency passed.
- Live Hindi and English POST requests returned HTTP 200 and four-page PDF downloads.
- UTF-8 attachment filenames, ASCII fallback, content length, no-store caching, and
	nosniff headers tested. Pages 2–4 remain visually identical to the template.
- Name-only, designation-only, city-only, full three-field, Hindi, English, mixed
	language, and exact whitespace forwarding cases tested.
- Missing/blank Name, non-string fields, nulls, unknown fields, over-limit fields,
	malformed JSON, unsupported glyphs, and text that cannot fit return HTTP 422.
- Validation responses omit submitted values and exception context. Internal/template
	failures return generic HTTP 500/503 responses without recipient text or internal paths.
- PDF generation calls are serialized within the process to avoid concurrent PyMuPDF use;
	bounded queues, rate limiting, request-body limits, and load testing remain Phase 7 work.
- Live missing-name validation returned HTTP 422; interactive API docs returned HTTP 200.
- Original template hashes are unchanged. Existing non-failing dependency warnings remain.
- Mobile frontend, automatic/fallback browser downloads, and Render/Linux checks remain unverified.

## Phase 5 verification

- Python suite: 112 tests, including 57 API tests. Frontend unit suite: 3 tests.
- Application and local CSS/JS/font are served from FastAPI; original PDF, PRD, and
	configuration files are not exposed through static mounts. No new runtime dependencies.
- Exact-preview endpoint: `POST /api/invitations/preview`, same strict recipient JSON
	as single generation; returns raw first-page PNG with no-store/nosniff headers.
	Invalid input/fit returns 422; unavailable template 503; unexpected error 500.
	Preview generation uses the same process-local lock and in-memory PDF service.
- Exact PNG and downloaded Page 1 are pixel-identical in tests for Hindi three-field,
	English Name + City, and English Name-only inputs. Existing four-page preservation tests pass.
- Browser checks: 320, 390, 768, and 1440 px layouts have no horizontal overflow.
	Screenshots checked at desktop and mobile widths; template/font assets and nonblank overlay render.
- Live typing makes no POST requests. The tested Hindi Name + City live ink bounds were
	within one pixel of exact output at 1.5x scale; a two-pixel edge tolerance at that scale
	is the local comparison criterion. Other browsers/fonts may rasterize differently,
	so use the exact preview for final approval.
- Blank Name disables actions. Empty optional fields compact correctly; full strings remain intact.
	Overlong entries produce a manual-correction error. Network failure preserves inputs and allows retry.
	Edits during preview/PDF requests discard stale results; editing revokes old blob URLs.
- Browser generation produced a valid PDF blob and correct Hindi filename, preserved form values,
	and exposed functioning PDF bytes through the manual fallback link. The integrated browser
	did not emit a download event, so saving to the operating-system Downloads folder was not
	independently verified. Real iOS Safari and Android Chrome saving still require device checks.
- Public deployment, Linux/Render checks, bulk processing, and Phase 7 resource controls remain deferred.