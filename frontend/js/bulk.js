import { createPreview } from './preview.js';

const element = id => document.getElementById(id);
const fileInput = element('bulk-file');
const validateButton = element('bulk-validate');
const generateButton = element('bulk-generate');
const verifyButton = element('bulk-verify');
const sampleSelect = element('bulk-sample-select');
let revision = 0;
let sampleRevision = 0;
let busy = false;
let report;
let render;
let zipURL;
let exactURL;

function fileIsValid() {
  const file = fileInput.files[0];
  return file && /\.xlsx$/i.test(file.name) && file.size <= 5 * 1024 * 1024;
}

function updateButtons() {
  validateButton.disabled = busy || !fileIsValid();
  generateButton.disabled = busy || !report?.valid_recipients;
  verifyButton.disabled = busy || !render || !report?.preview_records?.length;
  sampleSelect.disabled = busy;
  element('bulk-panel').setAttribute('aria-busy', String(busy));
}

function clearZIP() {
  element('bulk-download-panel').hidden = true;
  element('bulk-download').removeAttribute('href');
  if (zipURL) URL.revokeObjectURL(zipURL);
  zipURL = undefined;
}

function clearExact() {
  sampleRevision += 1;
  const image = element('bulk-exact-image');
  image.hidden = true;
  image.removeAttribute('src');
  if (exactURL) URL.revokeObjectURL(exactURL);
  exactURL = undefined;
  element('bulk-preview-kind').textContent = 'Live · approximate';
}

function showError(message) {
  element('bulk-error').textContent = message;
  element('bulk-error').hidden = false;
}

function showSummary(summary) {
  const list = element('bulk-summary');
  list.replaceChildren();
  for (const [key, title] of Object.entries({ total_rows: 'Excel data rows', valid_recipients: 'Valid recipients',
    generated: 'PDFs generated', skipped: 'Skipped rows', failed: 'Failed rows', layout_warnings: 'Layout warnings' })) {
    const label = document.createElement('dt');
    const value = document.createElement('dd');
    label.textContent = title;
    value.textContent = summary[key] ?? 0;
    list.append(label, value);
  }
  list.hidden = false;
}

function showIssues(records) {
  const list = element('bulk-issue-list');
  list.replaceChildren();
  for (const record of records.filter(row => ['failed', 'skipped'].includes(row.status))) {
    const item = document.createElement('li');
    item.textContent = `Row ${record.row}: ${record.status === 'skipped' ? 'Skipped — Name is blank.' : record.message}`;
    list.append(item);
  }
  element('bulk-issues').hidden = !list.childElementCount;
}

function selectedRecipient() {
  const sample = report?.preview_records?.[Number(sampleSelect.value)];
  return sample && { name: sample.name, second_line: sample.second_line, city: sample.city };
}

function drawSample() {
  clearExact();
  const recipient = selectedRecipient();
  if (!recipient || !render) return;
  element('bulk-sample-text').textContent = [recipient.name, recipient.second_line, recipient.city].filter(value => value.trim()).join('\n');
  render(recipient);
}

fileInput.addEventListener('change', () => {
  revision += 1;
  report = undefined;
  render = undefined;
  clearZIP();
  clearExact();
  element('bulk-samples').hidden = true;
  element('bulk-preview-empty').hidden = false;
  element('bulk-summary').hidden = element('bulk-issues').hidden = element('bulk-error').hidden = true;
  sampleSelect.replaceChildren();
  element('bulk-status').textContent = fileInput.files.length ? 'Workbook selected. Validate it to review recipients.' : 'Choose a workbook to begin.';
  if (fileInput.files.length && !fileIsValid()) showError('Choose an .xlsx workbook no larger than 5 MB.');
  updateButtons();
});

sampleSelect.addEventListener('change', drawSample);

async function responseError(response, currentRevision) {
  try {
    const payload = await response.json();
    if (payload.summary && revision === currentRevision) {
      showSummary(payload.summary);
      showIssues(payload.summary.records);
    }
    if (typeof payload.detail === 'string') return payload.detail;
  } catch {}
  return 'Unable to process the workbook. Please try again.';
}

async function upload(action) {
  if (busy || !fileIsValid() || action === 'generate' && !report?.valid_recipients) return;
  const currentRevision = revision;
  busy = true;
  updateButtons();
  clearZIP();
  element('bulk-error').hidden = true;
  element('bulk-status').textContent = action === 'validate' ? 'Validating workbook and checking text layout…' : `Generating ${report.valid_recipients} invitations and preparing ZIP…`;
  try {
    const body = new FormData();
    body.append('file', fileInput.files[0]);
    const response = await fetch(`/api/invitations/bulk/${action}`, { method: 'POST', body, cache: 'no-store' });
    if (revision !== currentRevision) return;
    if (!response.ok) throw new Error(await responseError(response, currentRevision));
    if (action === 'validate') {
      const result = await response.json();
      if (revision !== currentRevision) return;
      report = result;
      showSummary(result);
      showIssues(result.records);
      sampleSelect.replaceChildren();
      result.preview_records.forEach((sample, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = `Sample ${index + 1} · Row ${sample.row} · ${sample.name}`;
        sampleSelect.append(option);
      });
      element('bulk-status').textContent = result.valid_recipients
        ? 'Validation complete. Review the sample recipients, then confirm Generate all.'
        : 'No valid recipients. Correct the reported rows and upload the workbook again.';
      if (result.preview_records.length) {
        const layoutResponse = await fetch('/api/template/layout', { cache: 'no-store' });
        if (!layoutResponse.ok) throw new Error('Unable to load sample layout. Please validate again.');
        const configuration = await layoutResponse.json();
        const fonts = await document.fonts.load('16px Invitation');
        if (!fonts.length) throw new Error('Unable to load the invitation font. Please reload.');
        await element('bulk-template-image').decode();
        if (revision !== currentRevision) return;
        render = createPreview(element('bulk-text-overlay'), configuration);
        drawSample();
        element('bulk-samples').hidden = false;
        element('bulk-preview-empty').hidden = true;
      }
    } else {
      if (!response.headers.get('Content-Type')?.startsWith('application/zip')) throw new Error('The server returned an unexpected file. Please try again.');
      const counts = JSON.parse(response.headers.get('X-Generation-Summary'));
      const blob = await response.blob();
      if (revision !== currentRevision) return;
      zipURL = URL.createObjectURL(blob);
      const link = element('bulk-download');
      link.href = zipURL;
      element('bulk-download-panel').hidden = false;
      showSummary(counts);
      const failed = new Set(counts.failed_rows);
      showIssues(report.records.map(row => failed.has(row.row) && row.status === 'valid'
        ? { ...row, status: 'failed', message: 'Generation failed. See summary.json in the ZIP for the report.' } : row));
      link.click();
      element('bulk-status').textContent = `${counts.generated} PDFs ready · ${(blob.size / 1024 / 1024).toFixed(1)} MiB ZIP. Download requested; the fallback link is available below.`;
    }
  } catch (error) {
    if (revision !== currentRevision) return;
    showError(error instanceof TypeError ? 'Cannot reach the server. Check your connection and try again.' : error.message);
    element('bulk-status').textContent = 'Request failed. Your selected workbook has been kept.';
    if (action === 'validate') report = undefined;
  } finally {
    busy = false;
    updateButtons();
  }
}

async function verifySample() {
  const recipient = selectedRecipient();
  if (busy || !recipient || !render) return;
  const currentRevision = revision;
  clearExact();
  const currentSample = sampleRevision;
  busy = true;
  updateButtons();
  element('bulk-error').hidden = true;
  element('bulk-status').textContent = 'Rendering exact sample preview…';
  try {
    const response = await fetch('/api/invitations/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recipient), cache: 'no-store',
    });
    if (revision !== currentRevision || sampleRevision !== currentSample) return;
    if (!response.ok) throw new Error(await responseError(response, currentRevision));
    if (!response.headers.get('Content-Type')?.startsWith('image/png')) throw new Error('The server returned an unexpected preview.');
    const blob = await response.blob();
    if (revision !== currentRevision || sampleRevision !== currentSample) return;
    exactURL = URL.createObjectURL(blob);
    const image = element('bulk-exact-image');
    image.src = exactURL;
    await image.decode();
    if (revision !== currentRevision || sampleRevision !== currentSample) return;
    image.hidden = false;
    element('bulk-preview-kind').textContent = 'Exact · PDF renderer';
    element('bulk-status').textContent = 'Exact sample ready. Generate all when you have finished reviewing.';
  } catch (error) {
    if (revision !== currentRevision || sampleRevision !== currentSample) return;
    showError(error instanceof TypeError ? 'Cannot reach the server. Please try again.' : error.message);
    element('bulk-status').textContent = 'Sample preview failed. You can retry.';
  } finally {
    busy = false;
    updateButtons();
  }
}

validateButton.addEventListener('click', () => upload('validate'));
generateButton.addEventListener('click', () => upload('generate'));
verifyButton.addEventListener('click', verifySample);
window.addEventListener('pagehide', () => { clearZIP(); clearExact(); });
updateButtons();