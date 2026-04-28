/* ─────────────────────────────────────────────
   KYLO — API Client
   All fetch() calls to FastAPI backend
───────────────────────────────────────────── */

const API_BASE = '';

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

const API = {
  // Status
  status: () => apiFetch('/api/status'),
  config: () => apiFetch('/api/config'),
  saveConfig: (cfg) => apiFetch('/api/config', { method: 'PUT', body: JSON.stringify(cfg) }),

  // Files
  listFiles: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
    ).toString();
    return apiFetch(`/files${qs ? '?' + qs : ''}`);
  },
  getFile: (id) => apiFetch(`/files/${id}`),
  getSubjects: () => apiFetch('/files/subjects'),
  previewUrl: (id) => `${API_BASE}/files/${id}/preview`,
  renameFile: (id, newName) => apiFetch(`/files/${id}/rename`, {
    method: 'PUT', body: JSON.stringify({ new_name: newName })
  }),
  toggleStar: (id, starred) => apiFetch(`/files/${id}/star`, {
    method: 'PUT', body: JSON.stringify({ starred })
  }),
  updateNote: (id, note) => apiFetch(`/files/${id}/note`, {
    method: 'PUT', body: JSON.stringify({ note })
  }),
  moveToTrash: (id) => apiFetch(`/files/${id}/bin`, { method: 'POST' }),
  sendToWiki: (id) => apiFetch(`/files/${id}/send_to_wiki`, { method: 'POST' }),

  // Ingest
  listInbox: () => apiFetch('/ingest/inbox'),
  processFile: (filename) => apiFetch(`/ingest/process/${encodeURIComponent(filename)}`, { method: 'POST' }),
  approveIngest: (payload) => apiFetch('/ingest/approve', {
    method: 'POST', body: JSON.stringify(payload)
  }),
  uploadFile: async (file) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/ingest/upload`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Upload failed');
    return res.json();
  },

  // Duplicates / Bin
  listBin: () => apiFetch('/duplicates/bin'),
  restoreFromBin: (binId) => apiFetch(`/duplicates/bin/${binId}/restore`, { method: 'POST' }),
  permanentDelete: (binId) => apiFetch(`/duplicates/bin/${binId}?confirmed=true`, { method: 'DELETE' }),
  mergeFiles: (idA, idB) => apiFetch('/duplicates/merge', {
    method: 'POST', body: JSON.stringify({ file_id_a: idA, file_id_b: idB })
  }),

  // Query
  query: (question, topK = 5) => apiFetch('/query', {
    method: 'POST', body: JSON.stringify({ question, top_k: topK })
  }),

  // Tags
  listTags: () => apiFetch('/tags'),
  addTag: (fileId, tag) => apiFetch(`/tags/${fileId}`, {
    method: 'POST', body: JSON.stringify({ tag })
  }),
  removeTag: (fileId, tagName) => apiFetch(`/tags/${fileId}/${encodeURIComponent(tagName)}`, {
    method: 'DELETE'
  }),

  // Undo
  getUndoLog: () => apiFetch('/undo'),
  revertSession: (sessionId) => apiFetch(`/undo/session/${sessionId}/revert`, { method: 'POST' }),
};
