/* KYLO — File Preview */

const Preview = (() => {
  function open(fileId, filename) {
    const modal = document.getElementById('preview-modal');
    const nameEl = document.getElementById('preview-filename');
    const content = document.getElementById('preview-content');

    nameEl.textContent = filename || `File #${fileId}`;
    content.innerHTML = '';
    modal.classList.remove('hidden');

    const url = API.previewUrl(fileId);
    const ext = (filename || '').split('.').pop().toLowerCase();

    if (['jpg','jpeg','png','gif','webp','bmp','tiff'].includes(ext)) {
      content.innerHTML = `<img src="${url}" style="max-width:100%;max-height:70vh;border-radius:8px;" />`;
    } else if (ext === 'pdf') {
      content.innerHTML = `<iframe src="${url}" style="width:100%;height:70vh;border:none;border-radius:8px;"></iframe>`;
    } else {
      // Text-like
      content.innerHTML = '<div style="color:var(--color-muted);font-size:12px;padding:20px;">Loading…</div>';
      fetch(url)
        .then(r => r.text())
        .then(text => {
          content.innerHTML = `<pre style="font-family:var(--font-mono);font-size:12px;white-space:pre-wrap;max-height:70vh;overflow:auto;margin:0;">${escHtml(text.slice(0, 10000))}</pre>`;
        })
        .catch(() => {
          content.innerHTML = `<a href="${url}" target="_blank" class="btn-primary">Open file</a>`;
        });
    }
  }

  function close() {
    document.getElementById('preview-modal').classList.add('hidden');
  }

  function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  return { open, close };
})();
