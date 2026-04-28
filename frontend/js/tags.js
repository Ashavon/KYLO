/* KYLO — Tags Management */

const Tags = (() => {
  async function loadTagsView() {
    const el = document.getElementById('tags-list');
    el.innerHTML = '<div style="color:var(--color-muted);font-size:13px;">Loading…</div>';
    try {
      const data = await API.listTags();
      renderTagsView(data.tags || []);
    } catch (e) {
      el.innerHTML = `<div style="color:var(--color-danger);font-size:13px;">${e.message}</div>`;
    }
  }

  function renderTagsView(tags) {
    const el = document.getElementById('tags-list');
    if (!tags.length) {
      el.innerHTML = '<div style="color:var(--color-muted);font-size:13px;">No tags yet. Tags are created when you ingest files.</div>';
      return;
    }
    el.innerHTML = tags.map(t => `
      <div class="tag-item" onclick="App.filterByTag('${t.name}')">
        <span>🏷️</span>
        <span>${t.name}</span>
        <span class="badge-count">${t.count}</span>
      </div>
    `).join('');
  }

  async function addTagToFile(fileId, tagName) {
    if (!tagName.trim()) return;
    await API.addTag(fileId, tagName.trim().toLowerCase());
  }

  async function removeTagFromFile(fileId, tagName) {
    await API.removeTag(fileId, tagName);
  }

  function renderTagPills(tags, fileId, isAi = false) {
    if (!tags || !tags.length) return '';
    return tags.map(t => `
      <span class="tag-pill${isAi ? ' ai' : ''}" title="${isAi ? '✨ AI-generated' : 'User tag'}">${isAi ? '✨ ' : ''}${t}</span>
    `).join('');
  }

  return { loadTagsView, addTagToFile, removeTagFromFile, renderTagPills };
})();
