/* KYLO — Rename + Batch Rename */

const Rename = (() => {
  // Inline rename for a single file
  async function promptRename(fileId, currentName) {
    const newName = prompt('Rename file:', currentName);
    if (!newName || newName === currentName) return;
    try {
      await API.renameFile(fileId, newName);
      Explorer.refresh();
    } catch (e) {
      alert('Rename failed: ' + e.message);
    }
  }

  // Batch rename modal
  let _pendingBatch = [];

  async function openBatchModal(fileIds) {
    if (!fileIds.length) return;
    const modal = document.getElementById('batch-modal');
    const body = document.getElementById('batch-modal-body');
    modal.classList.remove('hidden');
    body.innerHTML = '<div style="padding:20px;color:var(--color-muted);">Running AI analysis…</div>';

    const results = [];
    for (const id of fileIds) {
      try {
        const file = await API.getFile(id);
        results.push(file);
      } catch (e) { /* skip */ }
    }
    _pendingBatch = results;
    renderBatchTable(results, body);
  }

  function renderBatchTable(rows, container) {
    const tableRows = rows.map((f, i) => `
      <tr>
        <td style="font-family:var(--font-mono);font-size:11px;">${escHtml(f.original_name || f.current_name)}</td>
        <td><input id="batch-name-${i}" value="${escHtml(f.current_name)}" /></td>
        <td><input id="batch-subj-${i}" value="${escHtml(f.subject || '')}" /></td>
        <td>
          <span class="confidence-bar-wrap">
            <span class="confidence-bar"><span class="confidence-fill ${confClass(f.ai_confidence)}" style="width:${Math.round((f.ai_confidence||0)*100)}%"></span></span>
            ${Math.round((f.ai_confidence||0)*100)}%
          </span>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <table class="batch-table">
        <thead><tr><th>Original</th><th>Proposed Name</th><th>Subject</th><th>Confidence</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table>
      <div class="batch-actions">
        <button class="btn-secondary" onclick="Rename.closeBatchModal()">Cancel</button>
        <button class="btn-primary" onclick="Rename.applyBatch()">✅ Apply All</button>
      </div>
    `;
  }

  async function applyBatch() {
    const errors = [];
    for (let i = 0; i < _pendingBatch.length; i++) {
      const file = _pendingBatch[i];
      const nameInput = document.getElementById(`batch-name-${i}`);
      if (!nameInput) continue;
      const newName = nameInput.value.trim();
      if (newName && newName !== file.current_name) {
        try {
          await API.renameFile(file.id, newName);
        } catch (e) {
          errors.push(`${file.current_name}: ${e.message}`);
        }
      }
    }
    closeBatchModal();
    Explorer.refresh();
    if (errors.length) alert('Some renames failed:\n' + errors.join('\n'));
  }

  function closeBatchModal() {
    document.getElementById('batch-modal').classList.add('hidden');
    _pendingBatch = [];
  }

  function confClass(c) {
    if (c >= 0.75) return 'conf-high';
    if (c >= 0.5) return 'conf-mid';
    return 'conf-low';
  }

  function escHtml(str) {
    return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { promptRename, openBatchModal, applyBatch, closeBatchModal };
})();
