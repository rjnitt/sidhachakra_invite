import { createPreview } from './preview.js';

const byId = id => document.getElementById(id);
const form = byId('recipient-form');
const inputs = [byId('name'), byId('second-line'), byId('city')];
const generate = byId('generate');
const verify = byId('verify');
let render;
let ready = false;
let busy = false;
let revision = 0;
let downloadURL;
let previewURL;

function recipient() {
  return { name: inputs[0].value, second_line: inputs[1].value, city: inputs[2].value };
}

function updateButtons() {
  generate.disabled = verify.disabled = !ready || busy || !inputs[0].value.trim();
  form.setAttribute('aria-busy', String(busy));
}

function clearDownload() {
  byId('download-panel').hidden = true;
  byId('download').removeAttribute('href');
  byId('open-pdf').removeAttribute('href');
  if (downloadURL) URL.revokeObjectURL(downloadURL);
  downloadURL = undefined;
}

function clearExact() {
  byId('exact-image').hidden = true;
  byId('exact-image').removeAttribute('src');
  if (previewURL) URL.revokeObjectURL(previewURL);
  previewURL = undefined;
  byId('preview-kind').textContent = 'Live · approximate';
}

function refresh() {
  revision += 1;
  clearDownload();
  clearExact();
  byId('error').hidden = true;
  if (render) byId('preview-text').textContent = render(recipient()).join(' · ');
  byId('status').textContent = ready ? 'Ready. Check the exact preview or generate your PDF.' : 'Loading invitation preview…';
  updateButtons();
}

async function errorMessage(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map(item => {
      const field = item.loc?.at(-1);
      return `${field || 'Input'}: ${item.msg || 'Invalid value'}`;
    }).join(' ');
  } catch {}
  return 'Unable to complete the request. Please try again.';
}

function filenameFromHeader(header = '') {
  const encoded = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) {
    try { return decodeURIComponent(encoded[1]); } catch {}
  }
  return header.match(/filename="([^"]+)"/i)?.[1] || 'Invitation.pdf';
}

async function submit(action) {
  if (busy || !ready || !form.reportValidity() || !inputs[0].value.trim()) return;
  const currentRevision = revision;
  busy = true;
  updateButtons();
  clearDownload();
  byId('error').hidden = true;
  byId('status').textContent = action === 'preview' ? 'Rendering exact preview…' : 'Generating your four-page PDF…';
  byId('preview-stage').setAttribute('aria-busy', String(action === 'preview'));
  try {
    const response = await fetch(`/api/invitations/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recipient()), cache: 'no-store',
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    const expectedType = action === 'preview' ? 'image/png' : 'application/pdf';
    if (!response.headers.get('Content-Type')?.startsWith(expectedType)) {
      throw new Error('The server returned an unexpected file. Please try again.');
    }
    const blob = await response.blob();
    if (revision !== currentRevision) return;
    if (action === 'preview') {
      clearExact();
      previewURL = URL.createObjectURL(blob);
      const image = byId('exact-image');
      image.src = previewURL;
      await image.decode();
      if (revision !== currentRevision) return;
      image.hidden = false;
      byId('preview-kind').textContent = 'Exact · PDF renderer';
      byId('status').textContent = 'Exact preview ready. Generate to download the complete four-page PDF.';
    } else {
      downloadURL = URL.createObjectURL(blob);
      const link = byId('download');
      link.href = downloadURL;
      link.download = filenameFromHeader(response.headers.get('Content-Disposition') || '');
      byId('open-pdf').href = downloadURL;
      byId('download-panel').hidden = false;
      link.click();
      byId('status').textContent = 'PDF ready. Your download has been requested; fallback links are available below.';
    }
  } catch (error) {
    if (revision !== currentRevision) return;
    byId('error').textContent = error instanceof TypeError
      ? 'Cannot reach the server. Check your connection and try again.' : error.message;
    byId('error').hidden = false;
    byId('status').textContent = 'Request failed. Your entries have been kept.';
  } finally {
    busy = false;
    byId('preview-stage').setAttribute('aria-busy', 'false');
    updateButtons();
  }
}

form.addEventListener('submit', event => { event.preventDefault(); submit('single'); });
verify.addEventListener('click', () => submit('preview'));
inputs.forEach(input => input.addEventListener('input', refresh));

for (const mode of ['single', 'bulk']) {
  byId(`${mode}-mode`).addEventListener('click', () => {
    for (const other of ['single', 'bulk']) {
      byId(`${other}-mode`).setAttribute('aria-pressed', String(other === mode));
      byId(`${other}-panel`).hidden = other !== mode;
    }
  });
}

async function initialize() {
  try {
    const response = await fetch('/api/template/layout', { cache: 'no-store' });
    if (!response.ok) throw new Error('Could not load invitation layout. Reload to retry.');
    const configuration = await response.json();
    const fonts = await document.fonts.load('16px Invitation');
    if (!fonts.length) throw new Error('Could not load the invitation font. Reload to retry.');
    await byId('template-image').decode();
    render = createPreview(byId('text-overlay'), configuration);
    ready = true;
    refresh();
  } catch {
    byId('error').textContent = 'Could not load the invitation preview or font. Check your connection and reload.';
    byId('error').hidden = false;
    byId('status').textContent = 'Invitation unavailable.';
  } finally {
    byId('preview-stage').setAttribute('aria-busy', 'false');
    updateButtons();
  }
}

window.addEventListener('pagehide', () => {
  if (downloadURL) URL.revokeObjectURL(downloadURL);
  if (previewURL) URL.revokeObjectURL(previewURL);
  downloadURL = previewURL = undefined;
  byId('download-panel').hidden = true;
  byId('exact-image').hidden = true;
});
initialize();