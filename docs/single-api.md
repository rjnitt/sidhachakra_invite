# Phase 4 Single-Generation API

Date: 2026-10-21. Phase 3 samples and Phase 4 execution were approved by the user.
The single-generation API and acceptance tests are complete. Phase 5 adds the frontend
and the exact-preview endpoint described below.

## Request

`POST /api/invitations/single` with `Content-Type: application/json`:

````json
{
  "name": "श्री सुरेन्द्र कुमार जैन",
  "second_line": "अध्यक्ष, जैन समाज",
  "city": "जबलपुर"
}
````

- `name`: required nonblank string, 1–500 characters.
- `second_line`: optional string, at most 500 characters, defaults to empty.
- `city`: optional string, at most 500 characters, defaults to empty.
- Optional fields may be omitted or empty; `null`, numbers, arrays, and objects are rejected.
- Extra fields are rejected. No automatic type coercion, trimming, spelling correction,
  honorific insertion, translation, or transliteration occurs.
- Unsupported glyphs and controls are rejected by the existing text-layout service.
- Field-length validation is not a promise that 500 rendered characters fit the rectangle.

Populated values retain fixed 16 pt text on consecutive writing rows. City becomes
row 2 when Second Line is empty. If both optional fields are empty, only the full
Name appears. Text that does not fit requires manual correction; it is never
automatically wrapped, shrunk, or silently clipped.

## Success

HTTP 200 with the complete four-page PDF as raw response bytes, not JSON or base64.

````text
Content-Type: application/pdf
Content-Disposition: attachment; filename="Invitation.pdf"; filename*=UTF-8''...
Cache-Control: no-store
X-Content-Type-Options: nosniff
Content-Length: <actual PDF byte count>
````

The UTF-8 parameter contains the safe Unicode filename from the PDF service.
ASCII-only filenames also appear in the plain `filename` parameter; Hindi or other
non-ASCII names use `Invitation.pdf` as the legacy fallback. Header values themselves
remain ASCII-safe. Duplicate names across independent single requests are allowed
because no generated files or global filename registry are stored.

Only Page 1 is personalized. Every original page dimension, image stream, and
Pages 2–4 are preserved by the Phase 3 service. The original template is never overwritten.

## Exact Preview

`POST /api/invitations/preview` accepts the identical recipient JSON and returns raw
`image/png` bytes for the personalized first page at 1.5x scale. It is generated
from the same four-page PDF service used by the download endpoint. For unchanged
input, template, and layout, the image is pixel-identical to downloaded Page 1.
It is not a PDF download and does not return Pages 2-4 or create files.

The browser requests this only when **Check exact preview** is selected, never on
each keystroke. The same process-local generation lock, safe error responses, and
`Cache-Control: no-store` apply. Successful PNG responses also use `nosniff`.
Both endpoints are independently stateless; no preview token or saved recipient is required.

## Errors

| Status | Meaning |
| --- | --- |
| 400 | Malformed or ambiguous body-length headers |
| 408 | Request body did not finish within 10 seconds |
| 413 | JSON request exceeds 16 KiB, including headers-declared or streamed bodies |
| 415 | Compressed/encoded request bodies are unsupported |
| 422 | Missing/invalid fields, malformed JSON, unsupported text, or unsafe 16 pt fit |
| 429 | More than 30 invitation attempts in 60 seconds; observe `Retry-After` |
| 503 | Generation is busy (`Retry-After: 1`) or the template is unavailable |
| 500 | Unexpected generation failure |

Schema errors return `detail` as a list containing only `loc`, `msg`, and `type`.
Unknown field names in `loc` are replaced with `unknown_field`; arbitrary submitted keys
are not echoed. Known recipient-field names and JSON error offsets remain useful for correction.
Submitted input values and exception context are omitted. Layout errors return a
clear message under `detail`, including the instruction to shorten overlong text
manually. Unexpected and template failures return generic messages with no internal
paths or recipient strings. Error responses use `Cache-Control: no-store`.

Generation calls are serialized by a process-local lock because PyMuPDF is not
safe for concurrent threads. Phase 7 also admits only one heavy request at a time
per application worker, including body reading and response sending. Other generation
requests receive 503 immediately instead of occupying an unbounded waiting queue.
The slot is released after failure, disconnect during upload, timeout, or completion.

Both single endpoints share a sliding-window rate limit of 30 attempts per 60 seconds
per ASGI client IP. Failed and busy attempts count too. At most 1,024 client buckets
are retained; expired entries are pruned on the next invitation attempt. When full,
new clients receive 429 until capacity is available. Raw forwarding headers are not
used as client identity. GET health, template assets, and the form are outside this quota.

The guard checks declared and actual streamed body size before JSON parsing. It rejects
duplicate/malformed Content-Length, conflicting transfer framing, mismatched lengths,
and compressed request bodies. Body reading has a total 10-second deadline. Existing
500-character field and safe-filename checks still apply; there is no change to typography.

The retained bulk POST routes share admission/rate controls and retain their existing
5 MiB upload allowance plus 64 KiB multipart overhead. Bulk UI remains paused; this
phase does not complete a public deployment review of workbook processing.

Responses include nosniff, no-referrer, frame-denial, and restricted browser permissions.
The home page additionally restricts scripts/styles/fonts/connections to this origin;
blob images remain allowed for exact previews. No new runtime dependency was added.

These are in-process controls, not distributed abuse prevention. Use one application
worker until deployment-level limits and trusted proxy configuration are reviewed.
Rate state resets on restart and is separate for each worker. Proxy headers must be
accepted only from a verified proxy that strips untrusted client headers; for direct
local use, `--no-proxy-headers` avoids forwarding-header spoofing. Connection/header
limits and hard CPU/process resource budgets must also be configured at deployment.

## Privacy and Runtime Behavior

The route sends JSON values directly to the existing immutable recipient model and
generates in memory using the cached original template and approved configuration.
It writes no uploaded or generated files and does not log request bodies or names.
There is no persistent request/job identifier, database, recipient history, or
cross-origin access enabled. The browser receives the PDF through the current request.

## Try Locally

Start the documented local Uvicorn command, then open `http://127.0.0.1:8000/docs`.
Expand `POST /api/invitations/single`, select **Try it out**, and submit the JSON.
OpenAPI describes the success response as a binary PDF download.

The [README](../README.md) also includes a curl download example. Client-side file
saving is a download, not server-side generated-file persistence.

## Verification

- `python -m pytest -q`: **94 passed**, including **39 API tests**.
- Dependency consistency passed; original PDF SHA-256 values remain unchanged.
- Hindi, English, mixed-script, name-only, designation-only, city-only, and full
  three-field requests return valid four-page PDFs.
- Response headers, exact input forwarding, UTF-8 filenames, and preserved Pages 2–4 tested.
- Invalid body types, field limits, nulls, unknown fields, missing names, malformed
  JSON, glyph errors, and overflow behavior tested.
- Mocked internal/template failures verify generic errors and released generation locks.
- Live Uvicorn requests verified Hindi and English downloads, safe missing-name
  HTTP 422 behavior, and API documentation availability.

The existing Hindi ligature copy/extraction limitation and non-failing dependency
deprecations remain. Mobile browser download behavior, production request limits,
rate limiting, Linux/Render rendering, and performance targets are not yet verified.

Obtain explicit approval before Phase 5: mobile frontend, live preview, automatic
download, and manual fallback.