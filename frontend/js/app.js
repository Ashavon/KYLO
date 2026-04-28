/* KYLO — App Init, State, Router */

const App = (() => {
  let _currentView = 'library';
  let _aiAvailable = true;

  async function init() {
    bindNav();
    bindHeader();
    bindDropZone();
    bindIngestModal();
    bindKeyboard();

    // Check AI status
    try {
      const status = await API.status();
      _aiAvailable = status.ollama_available;
      if (!_aiAvailable) {
        document.getElementById('ai-banner').classList.remove('hidden');
      }
    } catch (e) {
      _aiAvailable = false;
      document.getElementById('ai-banner').classList.remove('hidden');
    }

    // Load initial data
    await loadSubjectChips();
    await Explorer.load();
    await refreshInboxBadge();
  }

  function bindNav() {
    document.querySelectorAll('.sidebar-item').forEach(item => {
      item.addEventListener('click', e => {
        e.preventDefault();
        navigateTo(item.dataset.view);
      });
    });
  }

  function navigateTo(view) {
    _currentView = view;

    document.querySelectorAll('.sidebar-item').forEach(i =>
      i.classList.toggle('active', i.dataset.view === view)
    );
    document.querySelectorAll('.view').forEach(v =>
      v.classList.toggle('active', v.id === 'view-' + view)
    );

    switch (view) {
      case 'library':  Explorer.refresh(); break;
      case 'inbox':    loadInboxView(); break;
      case 'duplicates': Duplicates.loadBinView('duplicates'); break;
      case 'bin':      Duplicates.loadBinView('bin'); break;
      case 'tags':     Tags.loadTagsView(); break;
      case 'settings': loadSettingsView(); break;
    }
  }

  function bindHeader() {
    // Search
    const searchInput = document.getElementById('global-search');
    let searchTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        Explorer.setSearch(searchInput.value);
        if (_currentView !== 'library') navigateTo('library');
      }, 300);
    });

    // Undo
    document.getElementById('btn-undo').addEventListener('click', UndoPanel.toggle);
    document.getElementById('undo-close').addEventListener('click', UndoPanel.toggle);

    // Settings
    document.getElementById('btn-settings').addEventListener('click', () => navigateTo('settings'));

    // View toggles
    document.getElementById('btn-view-grid').addEventListener('click', () => Explorer.setGridMode(true));
    document.getElementById('btn-view-list').addEventListener('click', () => Explorer.setGridMode(false));

    // Batch actions
    document.getElementById('btn-batch-rename').addEventListener('click', () =>
      Rename.openBatchModal(Explorer.getSelectedIds())
    );
    document.getElementById('btn-batch-tag').addEventListener('click', () => Explorer.batchTag());
    document.getElementById('btn-batch-bin').addEventListener('click', () => Explorer.batchBin());

    // Load more
    document.getElementById('btn-load-more').addEventListener('click', () => Explorer.loadMore());

    // Ask KYLO
    document.getElementById('btn-ask-kylo').addEventListener('click', QueryPanel.toggle);
    document.getElementById('query-close').addEventListener('click', QueryPanel.close);
    document.getElementById('query-send').addEventListener('click', QueryPanel.sendQuery);
    document.getElementById('query-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') QueryPanel.sendQuery();
    });

    // Modals
    document.getElementById('preview-close').addEventListener('click', Preview.close);
    document.getElementById('preview-modal').addEventListener('click', e => {
      if (e.target === document.getElementById('preview-modal')) Preview.close();
    });
    document.getElementById('ingest-close').addEventListener('click', () =>
      document.getElementById('ingest-modal').classList.add('hidden')
    );
    document.getElementById('batch-close').addEventListener('click', Rename.closeBatchModal);
  }

  function bindDropZone() {
    const zone = document.getElementById('drop-zone');

    zone.addEventListener('dragover', e => {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', async e => {
      e.preventDefault();
      zone.classList.remove('dragover');
      const files = Array.from(e.dataTransfer.files);
      for (const file of files) {
        try {
          await API.uploadFile(file);
        } catch (err) {
          console.error('Upload failed:', err);
        }
      }
      await refreshInboxBadge();
      loadInboxView();
      if (_currentView !== 'inbox') navigateTo('inbox');
    });

    zone.addEventListener('click', () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = true;
      input.onchange = async () => {
        for (const file of Array.from(input.files)) {
          try {
            await API.uploadFile(file);
          } catch (err) {
            console.error('Upload failed:', err);
          }
        }
        await refreshInboxBadge();
        loadInboxView();
        if (_currentView !== 'inbox') navigateTo('inbox');
      };
      input.click();
    });
  }

  function bindIngestModal() {
    // Ingest modal is populated by the ingest flow
  }

  function bindKeyboard() {
    document.addEventListener('keydown', e => {
      if (e.ctrlKey && e.key === 'z') { e.preventDefault(); UndoPanel.toggle(); }
      if (e.key === '/' && !e.target.matches('input, textarea')) { e.preventDefault(); QueryPanel.toggle(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); document.getElementById('global-search').focus(); }
      if (e.key === 'Escape') {
        Preview.close();
        document.getElementById('ingest-modal').classList.add('hidden');
        document.getElementById('batch-modal').classList.add('hidden');
        closeAllMenus();
      }
    });
  }

  async function loadSubjectChips() {
    const container = document.getElementById('subject-chips');
    try {
      const data = await API.getSubjects();
      const subjects = data.subjects || [];

      const allChip = `<button class="subject-chip active" data-subject="" onclick="Explorer.setSubjectFilter(null);App.setAllChipActive()">All</button>`;
      const chips = subjects.map(s => {
        const subj = s.subject || 'Other';
        const style = getSubjectStyle(subj);
        return `<button class="subject-chip" data-subject="${subj}"
                  style="background:${style.bg};color:${style.text};border-color:${style.text}30"
                  onclick="Explorer.setSubjectFilter('${subj}')">
                  ${subj} <span class="chip-count">${s.count}</span>
                </button>`;
      });

      container.innerHTML = allChip + chips.join('');

      // Sidebar stats
      document.getElementById('stat-total').textContent = subjects.reduce((s, x) => s + x.count, 0);
      document.getElementById('stat-subjects').textContent = subjects.length;
    } catch (e) { /* silent */ }
  }

  function setAllChipActive() {
    document.querySelectorAll('.subject-chip').forEach(c => c.classList.remove('active'));
    document.querySelector('.subject-chip[data-subject=""]').classList.add('active');
  }

  function filterByTag(tagName) {
    Explorer.setFilter('tag', tagName);
    if (_currentView !== 'library') navigateTo('library');
    showActiveFilter('tag', tagName);
  }

  function showActiveFilter(type, value) {
    const el = document.getElementById('active-filters');
    el.classList.remove('hidden');
    el.innerHTML = `
      <span style="font-size:12px;color:var(--color-muted);">Filters:</span>
      <span class="filter-chip">
        ${type}: ${value}
        <span class="filter-remove" onclick="App.clearFilter('${type}')">✕</span>
      </span>
    `;
  }

  function clearFilter(type) {
    Explorer.setFilter(type, null);
    document.getElementById('active-filters').classList.add('hidden');
  }

  async function loadInboxView() {
    const list = document.getElementById('inbox-list');
    list.innerHTML = '<div style="color:var(--color-muted);font-size:13px;">Loading…</div>';
    try {
      const data = await API.listInbox();
      const files = data.files || [];
      if (!files.length) {
        list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📥</div><h3>Inbox is empty</h3><p>Drop files into the inbox to begin processing.</p></div>';
        return;
      }
      list.innerHTML = files.map(f => `
        <div class="inbox-item">
          <span class="inbox-item-name">${escHtml(f.name)}</span>
          <span class="inbox-item-size">${formatSize(f.size)}</span>
          <button class="btn-primary" style="padding:5px 14px;font-size:12px;" onclick="App.processInboxFile('${escHtml(f.name)}', this)">
            ✨ Process
          </button>
        </div>
      `).join('');
    } catch (e) {
      list.innerHTML = `<div style="color:var(--color-danger);font-size:13px;">${e.message}</div>`;
    }
  }

  async function processInboxFile(filename, btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Processing…';
    try {
      const result = await API.processFile(filename);
      showIngestApproval(result);
    } catch (e) {
      alert('Processing failed: ' + e.message);
      btn.disabled = false;
      btn.textContent = '✨ Process';
    }
  }

  function showIngestApproval(result) {
    const modal = document.getElementById('ingest-modal');
    const body = document.getElementById('ingest-modal-body');
    modal.classList.remove('hidden');

    const dups = result.duplicates || [];
    const dupHtml = dups.map(d => `
      <div class="dup-warning">
        ⚠️ Possible duplicate: <strong>${d.filename}</strong> (${d.level_name}, ${Math.round((d.score||0)*100)}% match)
      </div>
    `).join('');

    body.innerHTML = `
      ${dupHtml}
      <div class="ingest-proposed-name">${renderFilenameText(result.proposed_name)}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div class="ingest-field"><label>Subject</label>
          <input id="ig-subject" value="${escHtml(result.subject || '')}" /></div>
        <div class="ingest-field"><label>What</label>
          <input id="ig-what" value="${escHtml(result.what || '')}" /></div>
        <div class="ingest-field"><label>Where</label>
          <input id="ig-where" value="${escHtml(result.where || '')}" /></div>
        <div class="ingest-field"><label>Who</label>
          <input id="ig-who" value="${escHtml(result.who || '')}" /></div>
        <div class="ingest-field"><label>When</label>
          <input id="ig-when" value="${escHtml(result.when || '')}" /></div>
        <div class="ingest-field"><label>Tags (comma-separated)</label>
          <input id="ig-tags" value="${escHtml((result.tags || []).join(', '))}" /></div>
      </div>
      <div class="ingest-field" style="grid-column:1/-1">
        <label>Summary</label>
        <input id="ig-summary" value="${escHtml(result.summary || '')}" />
      </div>
      <div class="ingest-field">
        <label>Approved Filename</label>
        <input id="ig-name" value="${escHtml(result.proposed_name || '')}" />
      </div>
      <div class="ingest-actions">
        <button class="btn-secondary" onclick="document.getElementById('ingest-modal').classList.add('hidden')">Skip</button>
        <button class="btn-primary" onclick="App.approveIngest('${escHtml(result.inbox_path)}')">✅ Approve & Commit</button>
      </div>
    `;

    // Live filename preview
    ['ig-subject','ig-what','ig-where','ig-who','ig-when'].forEach(id => {
      document.getElementById(id).addEventListener('input', updateProposedName);
    });
  }

  function updateProposedName() {
    // Simple live preview — just join non-empty fields
    const ext = document.getElementById('ig-name').value.split('.').pop();
    const parts = ['ig-subject','ig-what','ig-where','ig-who','ig-when']
      .map(id => document.getElementById(id).value.trim())
      .filter(Boolean)
      .map(v => `[${v.replace(/\s+/g,'-')}]`);
    if (parts.length >= 2) {
      document.getElementById('ig-name').value = parts.join('_') + '.' + ext;
    }
  }

  async function approveIngest(inboxPath) {
    const tags = document.getElementById('ig-tags').value
      .split(',').map(t => t.trim()).filter(Boolean);
    const payload = {
      inbox_path: inboxPath,
      approved_name: document.getElementById('ig-name').value.trim(),
      subject: document.getElementById('ig-subject').value.trim(),
      what: document.getElementById('ig-what').value.trim(),
      where: document.getElementById('ig-where').value.trim(),
      who: document.getElementById('ig-who').value.trim(),
      when: document.getElementById('ig-when').value.trim(),
      summary: document.getElementById('ig-summary').value.trim(),
      tags,
    };
    try {
      await API.approveIngest(payload);
      document.getElementById('ingest-modal').classList.add('hidden');
      Explorer.refresh();
      await loadSubjectChips();
      await refreshInboxBadge();
    } catch (e) {
      alert('Commit failed: ' + e.message);
    }
  }

  async function refreshInboxBadge() {
    try {
      const data = await API.listInbox();
      const count = (data.files || []).length;
      const badge = document.getElementById('inbox-badge');
      if (count > 0) {
        badge.textContent = count;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    } catch (e) { /* silent */ }
  }

  async function loadSettingsView() {
    const form = document.getElementById('settings-form');
    let cfg = {};
    try { cfg = await API.config(); } catch (e) { /* use defaults */ }

    form.innerHTML = `
      <div class="settings-group">
        <h3>Paths</h3>
        ${settingRow('library_path', 'Library Path', cfg.library_path || './data/library')}
        ${settingRow('inbox_path', 'Inbox Path', cfg.inbox_path || './data/inbox')}
        ${settingRow('duplicates_bin_path', 'Duplicates Bin', cfg.duplicates_bin_path || './data/duplicates_bin')}
        ${settingRow('pkm_wiki_path', 'PKM Wiki Path', cfg.pkm_wiki_path || '')}
      </div>
      <div class="settings-group">
        <h3>AI Models</h3>
        ${settingRow('ollama_base_url', 'Ollama URL', cfg.ollama_base_url || 'http://localhost:11434')}
        ${settingRow('ollama_text_model', 'Text Model', cfg.ollama_text_model || 'gemma3:4b')}
        ${settingRow('ollama_vision_model', 'Vision Model', cfg.ollama_vision_model || 'gemma3:4b')}
        ${settingRow('ollama_embed_model', 'Embed Model', cfg.ollama_embed_model || 'nomic-embed-text')}
      </div>
      <div class="settings-group">
        <h3>Behaviour</h3>
        ${settingRow('semantic_dedup_threshold', 'Semantic Dedup Threshold (0–1)', cfg.semantic_dedup_threshold || 0.92)}
        ${settingRow('image_dedup_phash_threshold', 'Image pHash Threshold', cfg.image_dedup_phash_threshold || 10)}
      </div>
      <div class="settings-save">
        <button class="btn-primary" onclick="App.saveSettings()">💾 Save Settings</button>
      </div>
    `;
  }

  function settingRow(key, label, value) {
    return `
      <div class="settings-row">
        <label>${label}</label>
        <input id="cfg-${key}" value="${escHtml(String(value))}" />
      </div>
    `;
  }

  async function saveSettings() {
    const keys = ['library_path','inbox_path','duplicates_bin_path','pkm_wiki_path',
                   'ollama_base_url','ollama_text_model','ollama_vision_model','ollama_embed_model',
                   'semantic_dedup_threshold','image_dedup_phash_threshold'];
    const cfg = {};
    keys.forEach(k => {
      const el = document.getElementById('cfg-' + k);
      if (el) {
        const v = el.value.trim();
        cfg[k] = isNaN(v) || v === '' ? v : Number(v);
      }
    });
    try {
      await API.saveConfig(cfg);
      alert('Settings saved.');
    } catch (e) {
      alert('Save failed: ' + e.message);
    }
  }

  function renderFilenameText(name) {
    if (!name) return '';
    const parts = name.split('_');
    return parts.map((seg, i) => {
      const m = seg.match(/^(\[)([^\]]+)(\])(.*)$/);
      if (m) return `<span style="color:#cbd5e1">[</span>${m[2]}<span style="color:#cbd5e1">]</span>${m[4]}`;
      return seg;
    }).join('<span style="color:#94a3b8">_</span>');
  }

  function formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + 'KB';
    return (bytes / 1024 / 1024).toFixed(1) + 'MB';
  }

  function escHtml(str) {
    return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function getSubjectStyle(subject) {
    const map = {
      'Tax':      { bg: '#fef3c7', text: '#92400e' },
      'Health':   { bg: '#dcfce7', text: '#166534' },
      'Work':     { bg: '#dbeafe', text: '#1e40af' },
      'Finance':  { bg: '#f0fdf4', text: '#15803d' },
      'Travel':   { bg: '#ede9fe', text: '#6d28d9' },
      'Legal':    { bg: '#fee2e2', text: '#991b1b' },
      'Personal': { bg: '#fce7f3', text: '#9d174d' },
    };
    return map[subject] || { bg: '#f1f5f9', text: '#475569' };
  }

  return {
    init, navigateTo, filterByTag, clearFilter, setAllChipActive,
    processInboxFile, showIngestApproval, approveIngest, updateProposedName,
    loadInboxView, loadSettingsView, saveSettings,
  };
})();

// Boot
document.addEventListener('DOMContentLoaded', App.init);
