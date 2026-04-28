/* KYLO — Undo Panel */

const UndoPanel = (() => {
  let open = false;

  function toggle() {
    open = !open;
    const panel = document.getElementById('undo-panel');
    if (open) {
      panel.classList.remove('hidden');
      load();
    } else {
      panel.classList.add('hidden');
    }
  }

  async function load() {
    const list = document.getElementById('undo-list');
    list.innerHTML = '<div style="padding:16px;color:var(--color-muted);font-size:12px;">Loading…</div>';
    try {
      const data = await API.getUndoLog();
      render(data.sessions || []);
    } catch (e) {
      list.innerHTML = `<div style="padding:16px;color:var(--color-danger);font-size:12px;">${e.message}</div>`;
    }
  }

  function render(sessions) {
    const list = document.getElementById('undo-list');
    if (!sessions.length) {
      list.innerHTML = '<div style="padding:16px;color:var(--color-muted);font-size:12px;">No undo history yet.</div>';
      return;
    }
    list.innerHTML = sessions.map(s => `
      <div class="undo-session">
        <div class="undo-session-header">
          <span>${formatTs(s.timestamp)} — ${s.operations.length} op(s) [${s.status}]</span>
          ${s.status !== 'reverted' ? `<button class="undo-revert-session" onclick="UndoPanel.revertSession('${s.id}')">↩ Revert all</button>` : ''}
        </div>
        ${s.operations.map(op => `
          <div class="undo-op">
            <strong>${op.op}</strong>: ${shortPath(op.original_path)} → ${shortPath(op.new_path)}
          </div>
        `).join('')}
      </div>
    `).join('');
  }

  async function revertSession(id) {
    if (!confirm('Revert all operations in this session?')) return;
    try {
      await API.revertSession(id);
      load();
      Explorer.refresh();
    } catch (e) {
      alert('Revert failed: ' + e.message);
    }
  }

  function formatTs(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleString();
  }

  function shortPath(p) {
    if (!p) return '—';
    return p.split(/[/\\]/).pop();
  }

  return { toggle, load, revertSession };
})();
