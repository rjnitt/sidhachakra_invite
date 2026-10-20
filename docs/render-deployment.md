# Personal Render Deployment

Deploy the single-invitation application using your own GitHub and Render accounts.
Use Render's Python runtime. No Docker, database, API token, or application secret is needed.
You manage repository creation and publishing; no local Git setup has been performed.

## Before Publishing

1. Use a personal browser profile and personal email. Check the GitHub repository owner
   and Render workspace; do not select your employer's organization, SSO, or billing account.
2. Confirm you have permission to publish the code, PDF, and artwork. Personal accounts
   do not establish ownership or override an employer's policies on a managed device.
3. Start with a private personal repository while reviewing the source. A private repository
   does not make the Render website private: anyone with its URL can generate invitations
   and obtain all four pages, including any printed names, addresses, or phone numbers.
4. Resolve PyMuPDF licensing before launching publicly. PyMuPDF is AGPL/commercial;
   public hosting may require corresponding source under the applicable AGPL terms or
   a commercial license. Personal/noncommercial use does not automatically waive this.
   This project has not automatically been assigned a license. Keep the bundled font's OFL notice.

## Step 1: Publish the Personal Repository

Create the repository under your personal GitHub account, not a company organization.
Publish the project at the repository root, not inside an extra enclosing folder.
Include these deployment files:

```text
app/
assets/invitation.pdf
assets/fonts/NotoSansDevanagari.ttf
assets/fonts/OFL.txt
config/layout.json
frontend/
scripts/render_check.py
requirements.txt
render.yaml
```

Also include the README, documentation, and applicable license notices. Tests and
development requirements may be included, but generated test artifacts are unnecessary.

Do not publish `.venv`, `.vscode`, `.env` files, credentials, certificate/private-key files,
generated invitations, or `tests/artifacts`. The duplicate original at
`assets/fonts/invitation.pdf` is retained locally but is not needed for deployment.
When using GitHub's browser upload, exclude these manually; `.gitignore` does not filter
files you deliberately upload through the web interface.

Verify that `app/main.py`, `requirements.txt`, and `assets/invitation.pdf` appear at the
expected paths on GitHub before continuing. Never paste passwords or tokens into chat.

## Step 2: Connect Render

1. Sign in to your personal account at <https://dashboard.render.com/>.
2. Choose **New > Web Service**, then connect your personal GitHub account.
3. If asked to install the Render GitHub app, grant access only to this repository.
4. Select the repository and the branch you published. Confirm your personal workspace.

## Step 3: Configure the Service

| Setting | Value |
| --- | --- |
| Name | `jain-invitation-personalizer`, or another available personal name |
| Language/runtime | Python |
| Branch | Your published branch, commonly `main` |
| Root directory | Leave blank when the project is at repository root |
| Instance type | Free, if available and appropriate; do not select a paid plan unintentionally |
| Health check path | `/api/health` |
| Environment variable | `PYTHON_VERSION` = `3.12.14` |

Build command:

```bash
pip install -r requirements.txt && python -m scripts.render_check
```

Start command:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 16 --backlog 32 --timeout-keep-alive 5 --no-proxy-headers
```

Do not use `--reload`, multiple workers, wildcard proxy trust, or a hard-coded port.
Render supplies `PORT`; the app binds to all interfaces inside its service.
No secret key or persistent disk needs to be added.

These settings are also stored in `render.yaml`. The **Web Service** path requires
entering them in the dashboard; **New > Blueprint** is the alternative that reads that file.
Use one creation path, not both, to avoid duplicate services.

## Step 4: Deploy

Review the account, repository, plan, and licensing/privacy decisions above, then choose
**Create Web Service**. Render installs dependencies and runs the in-memory PDF check
on Linux before starting the app. Successful build output includes:

```text
Runtime check passed: startup, English/Hindi, four-page PDFs, unchanged Pages 2-4.
```

Wait for **Live**. Open the actual HTTPS `.onrender.com` URL shown by Render;
do not assume its hostname from the service name. The free tier can sleep when idle,
so the first request may be slow. Check current plan limits and pricing before creating it.

## Step 5: Verify the Public App

1. Visit `/api/health`; expect `{"status":"ok","template_loaded":true}`.
2. Open `/`; check the original invitation image and single-entry form.
3. Try an English Name + City, then a Hindi name with optional fields.
4. Check the exact preview and generate the four-page PDF. Inspect the downloaded file;
   confirm Pages 2-4 are unchanged and the recipient is correctly placed at 16 pt.
5. Test blank Name and an overlong name; they should not generate an invalid PDF.
6. Check `/api/invitations/bulk/template`; it should return 404.
7. On a real phone, test automatic download and the manual link. In iOS Safari,
   use Share > Save to Files if the browser opens the PDF instead of saving it.

Send the service URL and any redacted error text for further checks. Do not send tokens,
cookies, environment dumps, or actual private recipient lists.

## Limits and Recovery

- One heavy request runs at a time. Busy requests return 503 and `Retry-After: 1`.
- Generation and exact preview share 30 attempts per minute per observed client IP.
  Proxy headers are deliberately untrusted. Behind Render, users may share a proxy-IP
  bucket and receive 429 together; this is a conservative low-traffic starting policy,
  not verified per-user or distributed rate limiting.
- Rate state is in memory and resets on restart. Edge DDoS protection and authenticated
  access are not provided by this application.
- The app writes no recipient files. Render and its providers still process requests
  and retain infrastructure/access logs according to their own policies.
- A missing template/font build error usually means a required asset was not published
  or the root directory is wrong. Font files must keep their exact case-sensitive names.
- If a new deployment breaks, suspend it or use Render's rollback controls to return to
  the previous successful deployment. Re-run the health and Hindi PDF checks afterward.

Official references: [FastAPI on Render](https://render.com/docs/deploy-fastapi),
[Python versions](https://render.com/docs/python-version),
[Blueprint specification](https://render.com/docs/blueprint-spec).

## Preparation Evidence

- Secret scan: no confirmed credentials; two high-entropy findings were verified as
  template SHA-256 checksums. No credential-validation requests were sent.
- The old Starlette dependency had reported vulnerabilities. FastAPI/Starlette were
  upgraded; the resolved production audit then reported no known vulnerabilities.
  This does not certify that the application is vulnerability-free.
- The Render Blueprint passes Render's official JSON schema. Startup and English/Hindi
  generation pass with only production dependencies installed, without Excel packages.
- Local checks ran on macOS. No Docker was added, and no Linux/cloud deployment is
  claimed until Render's build and the public checks above succeed.