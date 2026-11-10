(() => {
  let mode = 'files', historyMode = 'files', revision = -1, entries = [];
  let fetching = false, sending = false, lastRender = '', request = null;
  const draft = $('textDraft');
  const historySort = document.querySelector('#history .sort');
  const shortcut = /Mac/.test(navigator.platform) ? '⌘ Enter' : 'Ctrl Enter';

  function buttons(first, second, isFirst) {
    $(first).setAttribute('aria-pressed', String(isFirst));
    $(second).setAttribute('aria-pressed', String(!isFirst));
  }

  function paintText() {
    const writing = mode === 'text', reading = historyMode === 'text';
    $('home').classList.toggle('writingText', writing);
    $('textComposer').hidden = !writing;
    $('currentTexts').hidden = !writing;
    $('fileHistoryTools').hidden = $('logs').hidden = reading;
    $('textHistoryTools').hidden = $('textLogs').hidden = !reading;
    buttons('modeFiles', 'modeText', !writing);
    buttons('historyFiles', 'historyText', !reading);
    $('sendText').disabled = sending || !state.canText || !draft.value.trim();
    $('sendText').textContent = sending ? '发送中…' : '发送文字';
    $('textHint').textContent = !state.peer ? '配对后即可发送' :
      !state.canText ? '请将两端更新至 1.8 以传输文字' : shortcut + ' 发送';
    $('clearTexts').disabled = entries.length === 0;
    const render = JSON.stringify([revision, state.pairID, sortOrder, writing, reading]);
    if (render === lastRender) return;
    lastRender = render;
    if (writing) showRows($('currentTexts'), entries.filter(row => state.peer && row.pairID === state.pairID), '本次连接还没有收发文字。');
    if (reading) showRows($('textLogs'), entries, '还没有文字记录。');
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        const input = document.createElement('textarea');
        input.value = text;
        document.body.append(input);
        input.select();
        const copied = document.execCommand('copy');
        input.remove();
        if (!copied) throw Error();
      }
      tell('文字已复制');
    } catch { tell('请选中文字后复制'); }
  }

  function showRows(list, items, empty) {
    const fragment = document.createDocumentFragment();
    for (const item of orderFiles(items)) {
      const article = node('article', '', 'textRow');
      const header = node('div', '', 'textMeta');
      const copy = node('button', '复制', 'secondary');
      copy.onclick = () => copyText(item.text);
      header.append(node('span', (item.out ? '发送给 ' : '来自 ') + item.peer), node('time', timeLabel(item)), copy);
      article.append(header, node('pre', item.text));
      fragment.append(article);
    }
    if (!items.length) fragment.append(node('p', empty, 'empty'));
    list.replaceChildren(fragment);
  }

  async function refresh() {
    paintText();
    if (fetching || state.textRevision == null || state.textRevision === revision) return;
    fetching = true;
    try {
      const data = await api('text/history');
      if (data.revision >= revision) {
        entries = data.items;
        revision = data.revision;
        paintText();
      }
    } catch (err) {
      if (mode === 'text' || historyMode === 'text') tell(err.message);
    } finally { fetching = false; }
  }

  $('modeFiles').onclick = () => { mode = 'files'; paintText(); };
  $('modeText').onclick = () => { mode = 'text'; refresh(); draft.focus(); };
  $('historyFiles').onclick = () => { historyMode = 'files'; paintText(); };
  $('historyText').onclick = () => { historyMode = 'text'; refresh(); };
  $('clearTexts').onclick = async () => {
    try {
      const data = await api('text/clear', {through: revision});
      revision = data.revision;
      entries = data.items;
      paintText();
      tell('文字记录已清空');
    } catch (err) { tell(err.message); }
  };
  draft.oninput = () => { request = null; paintText(); };
  draft.onkeydown = e => {
    if (!e.isComposing && e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (!$('sendText').disabled) $('textComposer').requestSubmit();
    }
  };
  $('textComposer').onsubmit = async e => {
    e.preventDefault();
    if ($('sendText').disabled || sending) return;
    const text = draft.value, pairID = state.pairID;
    if (!request || request.text !== text || request.pairID !== pairID) {
      const random = crypto.getRandomValues(new Uint8Array(16));
      request = {text, pairID, requestID: Array.from(random, b => b.toString(16).padStart(2, '0')).join('')};
    }
    sending = true;
    paintText();
    try {
      await api('text/send', request);
      if (draft.value === text) draft.value = '';
      request = null;
      tell('文字已发送');
      await sync();
    } catch (err) { tell(err.message); }
    finally { sending = false; paintText(); }
  };
  historySort.addEventListener('change', paintText);
  window.addEventListener('transfer-state', refresh);
  paintText();
})();
