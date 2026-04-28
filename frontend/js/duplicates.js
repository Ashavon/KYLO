/* KYLO — Duplicates & Bin */

const Duplicates = (() => {
  async function loadBinView(viewId) {
    const el = document.getElementById(viewId === 'bin' ? 'bin-grid' : 'duplicates-grid');
    el.innerHTML = '<div style="color:var(--color-muted);font-size:13px;padding:20px;">Loading…</div>';
    try {
      const data = await API.listBin();
      renderBin(data.bin || [], el);
    } catch (e) {
      el.innerHTML = `<div style="color:var(--color-danger);font-size:13px;padding:20px;">${e.message}</div>`;
    }
  }

  function renderBin(items, container) {
    if (!items.length) {
      container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🗑️</div><h3>Bin is empty</h3><p>Soft-deleted files appear here.</p></div>';
      return;
    }
    container.innerHTML = items.map(item => `
      <div class="dup-card">
        <div class="dup-card-header">
          <span class="dup-card-name">${escHtml(item.current_name || item.bin_path.split(/[/\\]/).pop())}</span>
        </div>
        <div class="dup-card-meta">
          <div>📅 Binned: ${fmtDate(item.date_binned)}</div>
          ${item.similarity_score ? `<div>Similarity: ${Math.round(item.similarity_score * 100)}%</div>` : ''}
          ${item.detection_level ? `<div>Level: ${item.detection_level}</div>` : ''}
        </div>
        <div class="dup-card-actions">
          <button class="dup-btn restore" onclick="Duplicates.restore(${item.id})">↩️ Restore</button>
          <button class="dup-btn delete" onclick="Duplicates.confirmDelete(${item.id}, '${escHtml(item.current_name || '')}')">🗑 Delete</button>
        </div>
      </div>
    `).join('');
  }

  async function restore(binId) {
    try {
      await API.restoreFromBin(binId);
      loadBinView('bin');
      loadBinView('duplicates');
      Explorer.refresh();
    } catch (e) {
      alert('Restore failed: ' + e.message);
    }
  }

  function confirmDelete(binId, filename) {
    const ok = confirm(
      `⚠️ PERMANENT DELETE\n\nThis will permanently delete:\n${filename}\n\nThis CANNOT be undone. Are you sure?`
    );
    if (!ok) return;
    const ok2 = confirm('Last chance — permanently delete this file?');
    if (!ok2) return;
    doDelete(binId);
  }

  async function doDelete(binId) {
    try {
      await API.permanentDelete(binId);
      loadBinView('bin');
      loadBinView('duplicates');
    } catch (e) {
      alert('Delete failed: ' + e.message);
    }
  }

  function showDupReview(fileA, fileB, duplicateInfo) {
    const modal = document.getElementById('ingest-modal');
    const body = document.getElementById('ingest-modal-body');
    modal.classList.remove('hidden');

    body.innerHTML = `
      <div class="dup-warning">
        ⚠️ Possible duplicate detected: <strong>${duplicateInfo.level_name}</strong>
        (score: ${Math.round((duplicateInfo.score || 0) * 100)}%)
      </div>
      <div class="dup-review-actions">
        <button class="btn-secondary" onclick="document.getElementById('ingest-modal').classList.add('hidden')">✕ Dismiss</button>
        <button class="btn-secondary" onclick="Duplicates.keepBoth()">Keep Both</button>
        <button class="btn-danger" onclick="Duplicates.softDeleteOlder(${fileB ? fileB.id : ''})">Soft-Delete Older</button>
      </div>
    `;
  }

  async function keepBoth() {
    document.getElementById('ingest-modal').classList.add('hidden');
  }

  async function softDeleteOlder(fileId) {
    if (!fileId) return;
    try {
      await API.moveToTrash(fileId);
      document.getElementById('ingest-modal').classList.add('hidden');
      Explorer.refresh();
    } catch (e) {
      alert('Failed: ' + e.message);
    }
  }

  function fmtDate(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString();
  }

  function escHtml(str) {
    return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { loadBinView, restore, confirmDelete, showDupReview, keepBoth, softDeleteOlder };
})();
