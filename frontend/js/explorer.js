/* KYLO — File Explorer (main file grid) */

const Explorer = (() => {
  let _files = [];
  let _total = 0;
  let _offset = 0;
  const _limit = 50;
  let _filters = { subject: null, tag: null, search: null, starred: null };
  let _selectedIds = new Set();
  let _gridMode = true; // true=grid, false=list

  async function load(append = false) {
    if (!append) {
      _offset = 0;
      _files = [];
    }

    const params = { ..._filters, limit: _limit, offset: _offset };
    try {
      const data = await API.listFiles(params);
      if (append) {
        _files = [..._files, ...data.files];
      } else {
        _files = data.files;
      }
      _total = data.total;
      _offset += data.files.length;
      render();
    } catch (e) {
      document.getElementById('file-grid').innerHTML =
        `<div style="color:var(--color-danger);font-size:13px;padding:20px;">${e.message}</div>`;
    }
  }

  function render() {
    const grid = document.getElementById('file-grid');
    grid.className = 'file-grid' + (_gridMode ? '' : ' list-mode');

    const countEl = document.getElementById('file-count');
    countEl.textContent = `${_total} file${_total !== 1 ? 's' : ''}`;

    if (!_files.length) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="empty-state-icon">📭</div>
          <h3>No files found</h3>
          <p>Drop files into the inbox or adjust your filters.</p>
        </div>`;
      document.getElementById('load-more-wrap').classList.add('hidden');
      return;
    }

    grid.innerHTML = _files.map(f => renderCard(f)).join('');

    // Load more button
    const lmWrap = document.getElementById('load-more-wrap');
    if (_offset < _total) {
      lmWrap.classList.remove('hidden');
    } else {
      lmWrap.classList.add('hidden');
    }

    updateBatchButtons();
  }

  function renderCard(f) {
    const subject = f.subject || '';
    const subjectClass = 'subj-' + (subject.toLowerCase() || 'other');
    const typePill = `<span class="pill pill-${f.file_type || 'other'}">${(f.file_type || 'file').toUpperCase()}</span>`;
    const filename = renderFilename(f.current_name, subject);
    const starClass = f.starred ? 'starred' : '';
    const summary = f.summary
      ? `<div class="card-summary">${escHtml(f.summary)}<span class="summary-ai-label">✨ AI</span></div>`
      : `<div class="summary-placeholder">Processing…</div>`;

    const tags = (f.tags || []);
    const tagHtml = tags.map(t => `<span class="tag-pill ai">✨ ${escHtml(t)}</span>`).join('') +
      `<button class="tag-add-btn" onclick="event.stopPropagation();Explorer.addTagInline(${f.id}, this)">+ tag</button>`;

    const ocrStatus = f.ocr_status || 'pending';
    const statusPills = [
      f.status === 'new' ? '<span class="pill pill-new">● NEW</span>' : '',
      f.status === 'binned' ? '<span class="pill pill-binned">IN BIN</span>' : '',
    ].filter(Boolean).join('');

    const conf = f.ai_confidence || 0;
    const confPct = Math.round(conf * 100);
    const confClass = conf >= 0.75 ? 'conf-high' : conf >= 0.5 ? 'conf-mid' : 'conf-low';
    const confWarning = conf < 0.75 ? ' ⚠' : '';

    const metrics = [
      f.page_count ? `📄 ${f.page_count}p` : '',
      f.word_count ? `📝 ${f.word_count}w` : '',
      f.row_count ? `📊 ${f.row_count}r` : '',
      f.dimensions ? `🖼 ${f.dimensions}` : '',
      f.file_size ? formatSize(f.file_size) : '',
      f.language ? `<span title="Language">${f.language}</span>` : '',
    ].filter(Boolean).join('<span style="color:#e2e8f0">·</span>');

    const wikiHtml = wikiPill(f.wiki_status, f.id);
    const origin = originIcon(f.origin);
    const dateAdded = fmtDate(f.date_added);

    const noteHtml = f.user_note
      ? `<div class="card-user-note" onclick="event.stopPropagation();Explorer.editNote(${f.id}, this)">📝 ${escHtml(f.user_note)}</div>`
      : '';

    const relatedHtml = (f.related_files || []).length
      ? `<div class="card-related">Related: ${(f.related_files || []).slice(0, 3).map(r =>
          `<span class="related-chip" onclick="event.stopPropagation();">${escHtml(r)}</span>`
        ).join('')}</div>`
      : '';

    const selected = _selectedIds.has(f.id) ? 'selected' : '';

    return `
      <div class="file-card ${selected}" data-id="${f.id}" data-subject="${escHtml(subject)}"
           onclick="Explorer.onCardClick(event, ${f.id}, '${escHtml(f.current_name)}')">
        <input type="checkbox" class="card-checkbox" ${selected ? 'checked' : ''}
               onclick="event.stopPropagation();Explorer.toggleSelect(${f.id}, this)" />
        <div class="card-header">
          <span class="card-type-pill">${typePill}</span>
          <span class="card-filename">${filename}</span>
          <button class="card-star ${starClass}" title="Star" onclick="event.stopPropagation();Explorer.toggleStar(${f.id}, ${f.starred})">
            ${f.starred ? '⭐' : '☆'}
          </button>
          <button class="card-menu-btn" title="More options" onclick="event.stopPropagation();Explorer.showMenu(event, ${f.id}, '${escHtml(f.current_name)}')">⋮</button>
        </div>
        ${summary}
        <div class="card-tags">${tagHtml}</div>
        <div class="card-status-bar">
          📅 ${f.when_field || dateAdded}
          <span class="ocr-indicator ocr-${ocrStatus}"><span class="ocr-dot"></span>OCR ${ocrStatus}</span>
          ${statusPills}
        </div>
        <div class="card-metrics">
          ${metrics}
          <span class="conf-bar-wrap" title="AI confidence">
            <span class="confidence-bar"><span class="confidence-fill ${confClass}" style="width:${confPct}%"></span></span>
            <span>${confPct}%${confWarning}</span>
          </span>
        </div>
        <div class="card-source-row">
          <span>${origin} ${dateAdded}</span>
          ${wikiHtml}
        </div>
        ${noteHtml}
        ${relatedHtml}
        <div class="card-hover-bar">
          <button class="hover-btn" onclick="event.stopPropagation();Preview.open(${f.id}, '${escHtml(f.current_name)}')">📂 Open</button>
          <button class="hover-btn" onclick="event.stopPropagation();Rename.promptRename(${f.id}, '${escHtml(f.current_name)}')">✏️ Rename</button>
          <button class="hover-btn" onclick="event.stopPropagation();QueryPanel.toggle()">💬 Ask AI</button>
          <button class="hover-btn danger" onclick="event.stopPropagation();Explorer.binFile(${f.id})">🗑 Bin</button>
        </div>
      </div>
    `;
  }

  function renderFilename(name, subject) {
    // Parse [Subject]_[What]_[Where]_[Who]_[When].ext
    const subjectLower = (subject || '').toLowerCase();
    const parts = name.split('_');
    return parts.map((seg, i) => {
      const isFirst = i === 0;
      const bracketMatch = seg.match(/^(\[)([^\]]+)(\])(.*)$/);
      if (bracketMatch) {
        const [, open, content, close, rest] = bracketMatch;
        if (isFirst && subject) {
          return `<span class="fn-bracket">[</span><span class="fn-subject ${subjectLower ? 'subj-' + subjectLower : ''}">${escHtml(content)}</span><span class="fn-bracket">]</span>${rest}`;
        }
        return `<span class="fn-bracket">[</span>${escHtml(content)}<span class="fn-bracket">]</span>${rest}`;
      }
      return escHtml(seg);
    }).join('<span class="fn-sep">_</span>');
  }

  function onCardClick(event, fileId, filename) {
    // Don't open on button clicks
    if (event.target.closest('button, input')) return;
    Preview.open(fileId, filename);
  }

  function toggleSelect(fileId, checkbox) {
    if (checkbox.checked) {
      _selectedIds.add(fileId);
    } else {
      _selectedIds.delete(fileId);
    }
    const card = document.querySelector(`.file-card[data-id="${fileId}"]`);
    if (card) card.classList.toggle('selected', checkbox.checked);
    updateBatchButtons();
  }

  function updateBatchButtons() {
    const hasSel = _selectedIds.size > 0;
    document.getElementById('btn-batch-rename').classList.toggle('hidden', !hasSel);
    document.getElementById('btn-batch-tag').classList.toggle('hidden', !hasSel);
    document.getElementById('btn-batch-bin').classList.toggle('hidden', !hasSel);
  }

  async function toggleStar(fileId, current) {
    try {
      await API.toggleStar(fileId, !current);
      refresh();
    } catch (e) { /* silent */ }
  }

  async function binFile(fileId) {
    if (!confirm('Move this file to the bin?')) return;
    try {
      await API.moveToTrash(fileId);
      refresh();
    } catch (e) {
      alert('Failed: ' + e.message);
    }
  }

  function showMenu(event, fileId, filename) {
    closeAllMenus();
    const menu = document.createElement('div');
    menu.className = 'card-context-menu';
    menu.id = 'active-ctx-menu';
    menu.innerHTML = `
      <div class="ctx-item" onclick="Preview.open(${fileId}, '${escHtml(filename)}');closeAllMenus()">📂 Open</div>
      <div class="ctx-item" onclick="Rename.promptRename(${fileId}, '${escHtml(filename)}');closeAllMenus()">✏️ Rename</div>
      <div class="ctx-item" onclick="QueryPanel.toggle();closeAllMenus()">💬 Ask AI about this</div>
      <div class="ctx-item" onclick="Explorer.sendToWiki(${fileId});closeAllMenus()">📤 Send to Wiki</div>
      <div class="ctx-item danger" onclick="Explorer.binFile(${fileId});closeAllMenus()">🗑 Move to Bin</div>
    `;
    menu.style.left = event.pageX + 'px';
    menu.style.top = event.pageY + 'px';
    document.body.appendChild(menu);
    setTimeout(() => document.addEventListener('click', closeAllMenus, { once: true }), 0);
  }

  function closeAllMenus() {
    const m = document.getElementById('active-ctx-menu');
    if (m) m.remove();
  }

  async function sendToWiki(fileId) {
    try {
      const r = await API.sendToWiki(fileId);
      if (r.status === 'sent') {
        refresh();
      } else {
        alert('Wiki send failed. Check pkm_wiki_path in Settings.');
      }
    } catch (e) {
      alert('Wiki send failed: ' + e.message);
    }
  }

  function addTagInline(fileId, btn) {
    const tag = prompt('Add tag:');
    if (!tag) return;
    Tags.addTagToFile(fileId, tag).then(() => refresh()).catch(e => alert(e.message));
  }

  function editNote(fileId, el) {
    const current = el.textContent.replace('📝 ', '').trim();
    const note = prompt('Edit note:', current);
    if (note === null) return;
    API.updateNote(fileId, note).then(() => refresh()).catch(e => alert(e.message));
  }

  function setFilter(key, value) {
    _filters[key] = value || null;
    refresh();
  }

  function setSubjectFilter(subject) {
    _filters.subject = subject;
    refresh();
    updateChipActiveState(subject);
  }

  function updateChipActiveState(subject) {
    document.querySelectorAll('.subject-chip').forEach(c => {
      c.classList.toggle('active', c.dataset.subject === subject);
    });
  }

  function setSearch(q) {
    _filters.search = q || null;
    refresh();
  }

  function setGridMode(grid) {
    _gridMode = grid;
    document.getElementById('btn-view-grid').classList.toggle('active', grid);
    document.getElementById('btn-view-list').classList.toggle('active', !grid);
    render();
  }

  function refresh() { load(false); }

  async function loadMore() { await load(true); }

  async function batchBin() {
    if (!_selectedIds.size) return;
    if (!confirm(`Move ${_selectedIds.size} file(s) to bin?`)) return;
    for (const id of _selectedIds) {
      try { await API.moveToTrash(id); } catch (e) { /* continue */ }
    }
    _selectedIds.clear();
    refresh();
  }

  async function batchTag() {
    const tag = prompt('Add tag to selected files:');
    if (!tag) return;
    for (const id of _selectedIds) {
      try { await API.addTag(id, tag); } catch (e) { /* continue */ }
    }
    refresh();
  }

  function getSelectedIds() { return [..._selectedIds]; }

  // ── Helper renderers ──

  function wikiPill(status, fileId) {
    if (status === 'in_wiki') return '<span class="wiki-pill-in">✅ In Wiki</span>';
    if (status === 'wiki_queued') return '<span class="wiki-pill-queued">⏳ Wiki queued</span>';
    return `<button class="wiki-pill-add" onclick="event.stopPropagation();Explorer.sendToWiki(${fileId})">➕ Add to Wiki</button>`;
  }

  function originIcon(origin) {
    const map = { scanned: '📷 Scanned', downloaded: '⬇ Downloaded', imported: '✏ Imported', created: '📝 Created' };
    return map[origin] || '✏ Imported';
  }

  function formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + 'KB';
    return (bytes / 1024 / 1024).toFixed(1) + 'MB';
  }

  function fmtDate(ts) {
    if (!ts) return '';
    return new Date(ts).toLocaleDateString();
  }

  function escHtml(str) {
    return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return {
    load, refresh, loadMore, render,
    onCardClick, toggleSelect, toggleStar, binFile, showMenu, addTagInline, editNote,
    sendToWiki, batchBin, batchTag, getSelectedIds, setFilter, setSubjectFilter, setSearch, setGridMode,
  };
})();

function closeAllMenus() {
  const m = document.getElementById('active-ctx-menu');
  if (m) m.remove();
}
