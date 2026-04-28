/* KYLO — AI Query Chat Panel */

const QueryPanel = (() => {
  let open = false;

  function toggle() {
    open = !open;
    const panel = document.getElementById('query-panel');
    if (open) {
      panel.classList.remove('hidden');
      document.getElementById('query-input').focus();
    } else {
      panel.classList.add('hidden');
    }
  }

  function close() {
    open = false;
    document.getElementById('query-panel').classList.add('hidden');
  }

  async function sendQuery() {
    const input = document.getElementById('query-input');
    const question = input.value.trim();
    if (!question) return;

    input.value = '';
    appendUserMessage(question);
    const typingEl = appendTypingIndicator();

    try {
      const result = await API.query(question);
      typingEl.remove();
      appendKyloMessage(result.answer, result.citations || []);
    } catch (e) {
      typingEl.remove();
      appendKyloMessage('Sorry, I encountered an error: ' + e.message, []);
    }
  }

  function appendUserMessage(text) {
    const msgs = document.getElementById('query-messages');
    const el = document.createElement('div');
    el.className = 'qmsg user';
    el.innerHTML = `<div class="qmsg-bubble">${escHtml(text)}</div>`;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function appendKyloMessage(text, citations) {
    const msgs = document.getElementById('query-messages');
    const el = document.createElement('div');
    el.className = 'qmsg kylo';

    const citationHtml = citations.length ? `
      <div class="qmsg-citations">
        ${citations.map(c => `
          <span class="citation-chip" onclick="Preview.open(${c.file_id || 'null'}, '${escHtml(c.filename)}')"
                title="${escHtml(c.filename)}">
            📄 ${escHtml(shortName(c.filename))}
          </span>
        `).join('')}
      </div>
    ` : '';

    el.innerHTML = `
      <div class="qmsg-bubble">${nl2br(escHtml(text))}</div>
      ${citationHtml}
    `;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function appendTypingIndicator() {
    const msgs = document.getElementById('query-messages');
    const el = document.createElement('div');
    el.className = 'qmsg kylo';
    el.innerHTML = `
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
    return el;
  }

  function shortName(name) {
    if (!name) return '?';
    return name.length > 30 ? name.slice(0, 27) + '…' : name;
  }

  function escHtml(str) {
    return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function nl2br(str) {
    return (str || '').replace(/\n/g, '<br>');
  }

  return { toggle, close, sendQuery };
})();
