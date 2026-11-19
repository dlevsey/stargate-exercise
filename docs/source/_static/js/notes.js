/* Your own highlights and notes on any page of the two sites.

   How to use it: select text on a page (a word, a line of code, a paragraph). Two buttons
   appear: "Highlight" marks the text, "Note" marks it and asks for a note. Click a mark to
   read, change or remove it. The "Notes" button at the bottom right lists every mark on
   every page, and saves them to a file or reads them back from one.

   Where they are kept: in this browser only (localStorage, under KEY below), for the address
   the site is served from. They are not written into the pages and not into the repository.
   Another browser, another port, or "clear site data" does not have them: use "Save to file"
   in the Notes list to keep a copy.

   How a mark finds its text again: it remembers the text itself and about 40 characters on
   either side, not a position. A rebuilt page keeps its marks as long as that text is still
   there. When the text is gone, the note stays in the Notes list, labelled as not found.

   Hover popups: the same works inside a popup. A popup shows a piece of another page, so a
   mark made there belongs to that page: it is also there when you open the page itself, and
   a mark made on a page shows in every popup of that piece. Selecting text in a popup pins
   the popup, so it stays open while you write. */
(function () {
  'use strict';
  const KEY = 'stargate-docs-notes-v1';
  const AROUND = 40;                       // characters remembered on either side of a mark
  // The name a page is kept under: its path on this site, its whole address for a page elsewhere.
  function keyOf(url) {
    if (url.origin !== location.origin) return url.origin + url.pathname;
    return url.pathname.endsWith('/') ? url.pathname + 'index.html' : url.pathname;
  }
  const page = keyOf(location);
  const main = document.querySelector('article.bd-article') || document.querySelector('main');
  if (!main) return;
  const POPUP = '.reference-preview-scroll[data-notes-page]';
  const pins = new WeakMap();              // the body of a popup -> the function that pins it
  // `root` is the piece of text being worked on: the page, or for a moment the body of a popup.
  let root = main;
  function within(element, work) { const was = root; root = element; try { return work(); } finally { root = was; } }
  function scopes() {
    return [{ root: main, page }, ...[...document.querySelectorAll(POPUP)].map((body) => ({ root: body, page: body.dataset.notesPage }))];
  }

  // ---- storage -----------------------------------------------------------------------------
  function load() {
    try { const found = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(found) ? found : []; }
    catch (error) { return []; }
  }
  function save(all) {
    try { localStorage.setItem(KEY, JSON.stringify(all)); }
    catch (error) { alert('The note could not be saved in this browser: ' + error.message); }
  }
  function update(change) { const all = load(); change(all); save(all); refresh(); }

  // ---- text of the page <-> places in it ------------------------------------------------------
  function textNodes() {
    // The line numbers beside code are not text of the page: a mark never covers or depends on them.
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => (node.parentElement.closest('.linenos') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const found = []; let start = 0;
    while (walker.nextNode()) { found.push({ node: walker.currentNode, start }); start += walker.currentNode.data.length; }
    return found;
  }
  function pageText(nodes) { return nodes.map((entry) => entry.node.data).join(''); }
  function offsetOf(nodes, container, offset) {
    const before = document.createRange();
    before.selectNodeContents(root);
    before.setEnd(container, offset);
    let count = 0;
    for (const entry of nodes) {
      if (entry.node === container) return entry.start + offset;
      if (before.comparePoint(entry.node, entry.node.data.length) > 0) break;    // this text starts after the place
      count = entry.start + entry.node.data.length;
    }
    return count;
  }
  function wrap(start, end, note) {
    const nodes = textNodes().filter((entry) => entry.start < end && entry.start + entry.node.data.length > start);
    for (const entry of nodes.reverse()) {          // from the end, so earlier places stay where they are
      let node = entry.node;
      const from = Math.max(0, start - entry.start), to = Math.min(node.data.length, end - entry.start);
      if (to < node.data.length) node.splitText(to);
      if (from > 0) node = node.splitText(from);
      if (!node.data.trim() && node.parentNode.closest('pre') === null) continue;   // no marks on empty space between blocks
      const mark = document.createElement('mark');
      mark.className = 'user-note' + (note.note ? ' has-note' : '');
      mark.dataset.noteId = note.id;
      if (note.note) mark.title = note.note;
      node.parentNode.insertBefore(mark, node);
      mark.appendChild(node);
    }
  }
  function place(note, text) {
    let at = text.indexOf(note.before + note.text + note.after);
    if (at >= 0) return at + note.before.length;
    at = text.indexOf(note.text);
    return at;
  }

  // ---- drawing the marks ----------------------------------------------------------------------
  let missing = new Set();
  function draw(scope) {
    within(scope.root, () => {
      for (const mark of root.querySelectorAll('mark.user-note')) {
        const parent = mark.parentNode;
        while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
        parent.removeChild(mark);
        parent.normalize();
      }
      for (const note of load().filter((entry) => entry.page === scope.page)) {
        const at = place(note, pageText(textNodes()));
        if (at >= 0) wrap(at, at + note.text.length, note);
        else if (root === main) missing.add(note.id);     // a popup shows only a piece of its page
      }
    });
  }
  function refresh() {
    missing = new Set();
    scopes().forEach(draw);
    drawCount();
    if (panel.classList.contains('open')) drawList();
  }

  // ---- the two buttons at a selection -----------------------------------------------------------
  const ui = document.createElement('div');
  ui.className = 'user-note-ui';
  ui.innerHTML =
    '<div class="user-note-bar" hidden><button type="button" data-do="highlight">Highlight</button>' +
    '<button type="button" data-do="note">Note</button></div>' +
    '<div class="user-note-card" hidden><textarea rows="4" placeholder="Your note"></textarea>' +
    '<div class="user-note-row"><button type="button" data-do="save">Save</button>' +
    '<button type="button" data-do="remove">Remove</button><button type="button" data-do="close">Close</button></div></div>' +
    '<button type="button" class="user-note-open" title="Your highlights and notes">Notes</button>' +
    '<div class="user-note-panel"><div class="user-note-row user-note-head"><strong>Your notes</strong>' +
    '<button type="button" data-do="export">Save to file</button><button type="button" data-do="import">Read from file</button>' +
    '<button type="button" data-do="hide">Close</button></div><div class="user-note-list"></div>' +
    '<input type="file" accept="application/json,.json" hidden></div>';
  document.body.appendChild(ui);
  const bar = ui.querySelector('.user-note-bar'), card = ui.querySelector('.user-note-card');
  const area = card.querySelector('textarea'), panel = ui.querySelector('.user-note-panel');
  const list = ui.querySelector('.user-note-list'), opener = ui.querySelector('.user-note-open');
  const picker = ui.querySelector('input[type=file]');
  let pending = null;      // the selection the two buttons are shown for
  let editing = null;      // the id of the note in the card

  function show(box, rect) {
    box.hidden = false;
    const width = box.offsetWidth, height = box.offsetHeight;
    let left = rect.left + rect.width / 2 - width / 2, top = rect.top - height - 8;
    if (top < 8) top = rect.bottom + 8;
    left = Math.max(8, Math.min(left, document.documentElement.clientWidth - width - 8));
    box.style.left = (left + scrollX) + 'px';
    box.style.top = (top + scrollY) + 'px';
  }
  function selected() {
    const selection = getSelection();
    if (!selection.rangeCount || selection.isCollapsed) return null;
    const range = selection.getRangeAt(0);
    const holder = range.commonAncestorContainer.nodeType === 1 ? range.commonAncestorContainer : range.commonAncestorContainer.parentElement;
    const popup = holder && holder.closest(POPUP);
    const place = popup || main;
    if (!place.contains(range.startContainer) || !place.contains(range.endContainer)) return null;
    return within(place, () => {
      const nodes = textNodes();
      const start = offsetOf(nodes, range.startContainer, range.startOffset), end = offsetOf(nodes, range.endContainer, range.endOffset);
      const text = pageText(nodes);
      if (!text.slice(start, end).trim()) return null;
      return {
        start, end, text, rect: range.getBoundingClientRect(), popup,
        page: popup ? popup.dataset.notesPage : page, title: popup ? popup.dataset.notesTitle : document.title,
      };
    });
  }
  document.addEventListener('mouseup', (event) => {
    if (ui.contains(event.target)) return;
    setTimeout(() => {                    // after the browser has settled the selection
      pending = selected();
      if (pending && pending.popup && pins.has(pending.popup)) pins.get(pending.popup)();   // keep the popup open
      if (pending) show(bar, pending.rect); else bar.hidden = true;
    }, 0);
  });
  document.addEventListener('mousedown', (event) => {
    if (ui.contains(event.target)) return;
    bar.hidden = true;
    if (!event.target.closest('mark.user-note')) card.hidden = true;
  });
  function add(withNote) {
    if (!pending) return;
    const { start, end, text, rect } = pending;
    const note = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7), page: pending.page, title: pending.title,
      text: text.slice(start, end), before: text.slice(Math.max(0, start - AROUND), start), after: text.slice(end, end + AROUND),
      note: '', made: new Date().toISOString(),
    };
    getSelection().removeAllRanges();
    bar.hidden = true; pending = null;
    update((all) => all.push(note));
    if (withNote) edit(note.id, rect);
  }
  function edit(id, rect) {
    const note = load().find((entry) => entry.id === id);
    if (!note) return;
    editing = id; area.value = note.note || '';
    show(card, rect); area.focus();
  }

  // ---- clicks -----------------------------------------------------------------------------------
  document.addEventListener('click', (event) => {
    const mark = event.target.closest('mark.user-note');
    if (!mark || !getSelection().isCollapsed) return;
    const popup = mark.closest(POPUP);
    if (popup && pins.has(popup)) pins.get(popup)();
    if (!event.target.closest('a')) event.preventDefault();
    edit(mark.dataset.noteId, mark.getBoundingClientRect());
  });
  ui.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    const action = button.dataset.do;
    if (button === opener) { panel.classList.toggle('open'); if (panel.classList.contains('open')) drawList(); }
    else if (action === 'highlight') add(false);
    else if (action === 'note') add(true);
    else if (action === 'save') { const id = editing, text = area.value.trim(); card.hidden = true; update((all) => { const note = all.find((entry) => entry.id === id); if (note) note.note = text; }); }
    else if (action === 'remove') { const id = editing; card.hidden = true; update((all) => { const at = all.findIndex((entry) => entry.id === id); if (at >= 0) all.splice(at, 1); }); }
    else if (action === 'close') card.hidden = true;
    else if (action === 'hide') panel.classList.remove('open');
    else if (action === 'export') exportNotes();
    else if (action === 'import') picker.click();
    else if (action === 'delete') { const id = button.dataset.id; update((all) => { const at = all.findIndex((entry) => entry.id === id); if (at >= 0) all.splice(at, 1); }); }
  });
  area.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) card.querySelector('[data-do=save]').click();
    if (event.key === 'Escape') card.hidden = true;
  });

  // ---- the list of all notes ------------------------------------------------------------------------
  function drawCount() {
    const here = load().filter((entry) => entry.page === page).length;
    opener.textContent = here ? 'Notes (' + here + ')' : 'Notes';
  }
  function drawList() {
    const all = load();
    list.textContent = '';
    if (!all.length) { list.textContent = 'Nothing yet. Select text on a page, then choose Highlight or Note.'; return; }
    const pages = new Map();
    for (const note of all) { if (!pages.has(note.page)) pages.set(note.page, []); pages.get(note.page).push(note); }
    const order = [...pages.keys()].sort((a, b) => (a === page ? -1 : b === page ? 1 : a.localeCompare(b)));
    for (const address of order) {
      const notes = pages.get(address);
      const head = document.createElement('a');
      head.className = 'user-note-page'; head.href = address;
      head.textContent = (notes[0].title || address).replace(/ — .*$/, '') + (address === page ? ' (this page)' : '');
      list.appendChild(head);
      for (const note of notes) {
        const item = document.createElement('div'); item.className = 'user-note-item';
        const quote = document.createElement('a');
        quote.className = 'user-note-quote'; quote.href = address + '#note-' + note.id;
        quote.textContent = note.text.length > 160 ? note.text.slice(0, 160) + '…' : note.text;
        item.appendChild(quote);
        if (note.note) { const words = document.createElement('div'); words.className = 'user-note-words'; words.textContent = note.note; item.appendChild(words); }
        if (address === page && missing.has(note.id)) { const lost = document.createElement('div'); lost.className = 'user-note-lost'; lost.textContent = 'This text is no longer on the page.'; item.appendChild(lost); }
        const remove = document.createElement('button');
        remove.type = 'button'; remove.dataset.do = 'delete'; remove.dataset.id = note.id; remove.textContent = 'Remove';
        item.appendChild(remove);
        list.appendChild(item);
      }
    }
  }
  function jump() {
    const found = /^#note-(.+)$/.exec(location.hash);
    const mark = found && root.querySelector('mark.user-note[data-note-id="' + CSS.escape(found[1]) + '"]');
    if (!mark) return;
    mark.scrollIntoView({ block: 'center' });
    for (const part of root.querySelectorAll('mark.user-note[data-note-id="' + CSS.escape(found[1]) + '"]')) {
      part.classList.add('flash'); setTimeout(() => part.classList.remove('flash'), 1600);
    }
  }
  window.addEventListener('hashchange', jump);

  // ---- hover popups -----------------------------------------------------------------------------------
  document.addEventListener('reference-preview:filled', (event) => {
    const { body, url, title, pin } = event.detail;
    body.dataset.notesPage = keyOf(new URL(url, location.href));
    body.dataset.notesTitle = title || '';
    pins.set(body, pin);
    draw({ root: body, page: body.dataset.notesPage });
  });

  // ---- a file with all notes -------------------------------------------------------------------------
  function exportNotes() {
    const file = new Blob([JSON.stringify(load(), null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(file); link.download = 'stargate-docs-notes.json';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }
  picker.addEventListener('change', () => {
    const file = picker.files[0];
    if (!file) return;
    file.text().then((content) => {
      const read = JSON.parse(content);
      if (!Array.isArray(read)) throw new Error('this is not a notes file');
      const good = read.filter((entry) => entry && typeof entry.id === 'string' && typeof entry.page === 'string' && typeof entry.text === 'string');
      update((all) => { for (const entry of good) if (!all.some((have) => have.id === entry.id)) all.push({ before: '', after: '', note: '', ...entry }); });
    }).catch((error) => alert('The file could not be read: ' + error.message)).finally(() => { picker.value = ''; });
  });

  // Other scripts of the page change it first (the marked lines of a file page, for one).
  function start() { setTimeout(() => { refresh(); jump(); }, 150); }
  if (document.readyState === 'complete') start(); else window.addEventListener('load', start);
  window.addEventListener('storage', (event) => { if (event.key === KEY) refresh(); });   // changed in another tab
})();
