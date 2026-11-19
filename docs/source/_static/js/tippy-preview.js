/*
 * Reference previews: a hover popup for links to pages, headings and C# names.
 * One initializer handles references, cards, and saved copies of pages on other sites.
 * A popup that stays open for a moment is pinned; links inside it open further popups.
 * A link to lines of a file (Program.cs.html#L6-L21) shows just those lines.
 * The popup library in ../vendor/tippy/ is described in ../vendor/tippy/PROVENANCE.txt.
 */
(() => {
  'use strict';

  const config = window.REFERENCE_PREVIEW_CONFIG;
  if (!config || window.REFERENCE_PREVIEWS_INITIALIZED) return;
  window.REFERENCE_PREVIEWS_INITIALIZED = true;

  const documents = new Map();
  const parser = new DOMParser();
  const staticBase = new URL('../', document.currentScript.src);
  // Addresses on other sites are compared without their #fragment and in lower case:
  // the same page is linked as System.Guid in one place and system.guid in another.
  const externalKey = url => {
    const key = new URL(url);
    key.hash = '';
    key.pathname = key.pathname.toLowerCase();
    return key.href;
  };
  // Saved copy of a page on another site: address -> full address of its JSON file (or null).
  const externalPages = new Map(Object.entries(config.externalPages || {}).map(
    ([url, asset]) => [externalKey(url), asset ? new URL(asset, staticBase).href : null]
  ));
  const open = [];              // every popup that is open, oldest first
  const pinDelay = config.pinDelay ?? 1000;
  let zTop = 10000;
  let suppressFocus = false;

  function targetURL(link) {
    if (!link || config.skipClasses.some(name => link.classList.contains(name)) ||
        link.closest('.no-preview, [data-no-preview]') ||
        link.hasAttribute('download') || !link.getAttribute('href')) return null;

    let url;
    try {
      url = new URL(link.getAttribute('href'), document.baseURI);
    } catch (_) {
      return null;
    }
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    if (url.origin !== location.origin) return externalPages.has(externalKey(url)) ? url : null;
    // Downloads, images, and email links keep ordinary navigation.
    if (!url.pathname.endsWith('/') && !/\.html?$/i.test(url.pathname)) return null;
    return url;
  }

  function currentDocument(url) {
    return url.origin === location.origin && url.pathname === location.pathname &&
      url.search === location.search;
  }

  async function loadDocument(url) {
    if (currentDocument(url)) return { doc: document, base: document.baseURI };
    const key = new URL(url);
    key.hash = '';
    if (!documents.has(key.href)) {
      const pending = (async () => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
          const external = key.origin !== location.origin;
          const asset = externalPages.get(externalKey(key));
          if (external && !asset) throw new Error('No saved preview available');
          const response = await fetch(external ? asset : key.href, {
            signal: controller.signal,
            credentials: 'same-origin',
          });
          const type = external ? 'application/json' : 'text/html';
          if (!response.ok || new URL(response.url).origin !== location.origin ||
              !response.headers.get('content-type')?.includes(type)) {
            throw new Error('Preview page unavailable');
          }
          if (external) {
            const saved = await response.json();
            if (new URL(saved.url).origin !== key.origin || typeof saved.html !== 'string') {
              throw new Error('Invalid saved preview');
            }
            return {
              doc: parser.parseFromString(saved.html, 'text/html'),
              base: saved.url,
              fetchedAt: saved.fetchedAt,
              saved: true,
            };
          }
          const doc = parser.parseFromString(await response.text(), 'text/html');
          return { doc, base: response.url };
        } finally {
          clearTimeout(timeout);
        }
      })();
      documents.set(key.href, pending);
      // Keep a bounded cache of fetched pages, shared by links to their sections.
      if (documents.size > 24) documents.delete(documents.keys().next().value);
      pending.catch(() => documents.delete(key.href));
    }
    return documents.get(key.href);
  }

  function definitionEntry(signature) {
    const entry = signature.parentElement.cloneNode(false);
    let node = signature;
    while (node.previousElementSibling?.matches('dt')) node = node.previousElementSibling;
    for (; node?.matches('dt'); node = node.nextElementSibling) entry.append(node.cloneNode(true));
    if (node?.matches('dd')) entry.append(node.cloneNode(true));
    return entry;
  }

  // A page of the dev docs that shows a repository file has every line of the file in
  // a <span id="L-6">. A link to it can name lines: "#L6" or "#L6-L21", as on GitHub. The
  // popup then shows those lines only, moved to the left as far as their indentation allows.
  function sourceLines(doc, article, first, last) {
    const lines = [];
    for (let number = first; number <= Math.max(first, last); number += 1) {
      const line = doc.getElementById(`L-${number}`);
      if (!line) break;
      lines.push(line.cloneNode(true));
    }
    const pre = doc.getElementById(`L-${first}`).closest('pre');
    if (!pre || !article.contains(pre)) throw new Error('Lines not found');
    // The text of a line without its number: what is left of the line once the number is skipped.
    const textNodes = line => {
      const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
      const found = [];
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.parentElement.closest('.linenos')) found.push(node);
      }
      return found;
    };
    const indents = lines.map(line => textNodes(line).map(node => node.data).join(''))
      .filter(text => text.trim()).map(text => text.match(/^[ \t]*/)[0].length);
    const shared = indents.length ? Math.min(...indents) : 0;
    lines.forEach(line => {
      let left = shared;
      for (const node of textNodes(line)) {
        const cut = Math.min(left, node.data.match(/^[ \t]*/)[0].length);
        node.data = node.data.slice(cut);
        left -= cut;
        if (!left || node.data) break;
      }
    });
    // The boxes around the lines are copied without their content, so the colours stay the same.
    let excerpt = pre.cloneNode(false);
    excerpt.append(...lines);
    for (let box = pre.parentElement; box && box !== article && box.matches('div'); box = box.parentElement) {
      const copy = box.cloneNode(false);
      copy.append(excerpt);
      excerpt = copy;
      if (/(^|\s)highlight-/.test(box.className)) break;
    }
    const file = article.querySelector('h1')?.textContent.replace(/[¶#]\s*$/, '').trim();
    const range = lines.length > 1 ? `lines ${first}–${first + lines.length - 1}` : `line ${first}`;
    excerpt.dataset.previewTitle = file ? `${file}, ${range}` : range;
    return excerpt;
  }

  function findContent(doc, url, saved) {
    // Query in priority order: a combined selector would choose an outer <main>
    // before its article and bring the page's sidebar/layout into the portal.
    const article = doc.querySelector('article.bd-article') || doc.querySelector('article') ||
      doc.querySelector('.rst-content') || doc.querySelector('[role="main"], main, .document');
    if (!article) throw new Error('No document content');
    if (!url.hash) return article;

    const place = decodeURIComponent(url.hash.slice(1));
    const lines = /^L(\d+)(?:-L?(\d+))?$/.exec(place);
    if (lines && doc.getElementById(`L-${lines[1]}`)) {
      return sourceLines(doc, article, Number(lines[1]), Number(lines[2] || lines[1]));
    }
    const target = doc.getElementById(place);
    if (!target || !article.contains(target)) {
      // A saved copy of a page on another site may not have the part that the link names
      // (one overload of a method, say). The whole saved page is still better than nothing.
      if (saved) return article;
      throw new Error('Section not found');
    }
    const signature = target.closest('dt');
    if (signature && article.contains(signature)) return definitionEntry(signature);
    // Sphinx labels can be empty spans immediately before the actual section.
    if (target.matches('span.target, span[id]') && !target.textContent.trim()) {
      let next = target.nextElementSibling;
      while (next?.matches('span[id]') && !next.textContent.trim()) next = next.nextElementSibling;
      if (next?.matches('section, .section')) return next;
      if (next?.matches('h1, h2, h3, h4, h5, h6')) {
        return next.closest('section, .section') || next;
      }
    }
    if (target.matches('h1, h2, h3, h4, h5, h6')) {
      return target.closest('section, .section') || target;
    }
    return target;
  }

  function cloneContent(content, base) {
    const clone = content.cloneNode(true);
    // Sphinx Design hides tab panels unless their radio input is checked. Since
    // previews strip those inputs, turn every tab into a readable labeled section
    // before removing controls. Nested tab sets retain their heading hierarchy.
    const tabSets = [
      ...(clone.matches('.sd-tab-set') ? [clone] : []),
      ...clone.querySelectorAll('.sd-tab-set'),
    ];
    tabSets.forEach(tabSet => {
      let level = 2;
      for (let outer = tabSet.parentElement?.closest('.reference-preview-tabs'); outer;
           outer = outer.parentElement?.closest('.reference-preview-tabs')) level += 1;
      tabSet.classList.replace('sd-tab-set', 'reference-preview-tabs');
      [...tabSet.children].forEach(child => {
        if (child.matches('.sd-tab-label')) {
          const heading = document.createElement(`h${Math.min(level, 6)}`);
          heading.textContent = child.textContent.trim();
          child.replaceWith(heading);
        } else if (child.matches('.sd-tab-content')) {
          child.classList.replace('sd-tab-content', 'reference-preview-tab-content');
          child.removeAttribute('hidden');
        }
      });
    });
    clone.querySelectorAll('object[type="image/svg+xml"][data]').forEach(diagram => {
      const image = document.createElement('img');
      image.setAttribute('src', diagram.getAttribute('data'));
      image.alt = 'Diagram (open the full page to click its parts)';
      diagram.replaceWith(image);
    });
    // Preview content is a passive copy; controls and site scripts remain on the page.
    clone.querySelectorAll(
      'script, style, link, meta, base, iframe, object, embed, form, input, button, ' +
      'textarea, select, svg, nav, .headerlink, .copybtn, .anchor-link, .backrefs'
    ).forEach(el => el.remove());

    [clone, ...clone.querySelectorAll('*')].forEach(el => {
      el.removeAttribute('id');
      el.removeAttribute('autofocus');
      el.removeAttribute('aria-labelledby');
      el.removeAttribute('aria-describedby');
      // Use the fallback image src so responsive candidates cannot resolve from
      // the page hosting the portal instead of the page being previewed.
      el.removeAttribute('srcset');
      for (const attr of [...el.attributes]) {
        if (attr.name.startsWith('on')) el.removeAttribute(attr.name);
      }
      for (const attr of ['href', 'src', 'poster']) {
        const value = el.getAttribute(attr);
        if (!value) continue;
        const resolved = new URL(value, base);
        if (['http:', 'https:', 'mailto:', 'tel:'].includes(resolved.protocol) ||
            (attr === 'src' && /^data:image\//i.test(value))) {
          el.setAttribute(attr, resolved.href);
        } else {
          el.removeAttribute(attr);
        }
      }
      if (el.matches('a')) {
        el.removeAttribute('data-tippy-content');
      }
    });
    // The theme gives article.bd-article its own page-width and spacing rules.
    // Keep its contents without importing that outer layout into a small panel.
    if (clone.matches('article')) {
      const wrapper = document.createElement('div');
      wrapper.append(...clone.childNodes);
      return wrapper;
    }
    return clone;
  }

  // A pinned popup refuses to close (onHide returns false) until it is unpinned.
  function pin(tip) {
    clearTimeout(tip.pin.timer);
    tip.pin.pinned = true;
    tip.popper.classList.remove('pin-off');
    tip.popper.classList.add('is-pinned');
  }

  // Unpinned, but still open until the pointer or the keyboard focus leaves it.
  function unpin(tip) {
    clearTimeout(tip.pin.timer);
    tip.pin.pinned = false;
    tip.popper.classList.remove('is-pinned');
    tip.popper.classList.add('pin-off');
  }

  function forget(tip) {
    clearTimeout(tip.pin.timer);
    tip.pin.pinned = false;
    tip.popper.classList.remove('is-pinned', 'pin-off');
    const at = open.indexOf(tip);
    if (at >= 0) open.splice(at, 1);
  }

  // Closes a popup and every popup that was opened from inside it.
  function closeTip(tip, restoreFocus = false) {
    open.filter(other => other.pin.parent === tip).forEach(child => closeTip(child));
    forget(tip);
    if (restoreFocus && document.contains(tip.reference)) {
      suppressFocus = true;
      tip.reference.focus({ preventScroll: true });
      suppressFocus = false;
    }
    tip.hide();
  }

  function previewShell(instance, url, title) {
    const shell = document.createElement('div');
    shell.className = 'reference-preview';
    shell.style.setProperty('--reference-preview-height', `${config.maxHeight}px`);
    const header = document.createElement('div');
    header.className = 'reference-preview-header';
    const heading = document.createElement('strong');
    heading.className = 'reference-preview-title';
    heading.textContent = title;
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'reference-preview-close';
    closeButton.setAttribute('aria-label', 'Close reference preview');
    closeButton.textContent = '×';
    closeButton.addEventListener('click', () => closeTip(instance, true));
    // The ring fills while the popup is open; a full ring means the popup is pinned.
    const ring = document.createElement('button');
    ring.type = 'button';
    ring.className = 'reference-preview-pin';
    ring.title = 'Fills while you hover. When full, this preview stays open. Click to pin or unpin now.';
    ring.setAttribute('aria-label', 'Keep this preview open');
    ring.style.setProperty('--pin-ms', `${pinDelay}ms`);
    ring.addEventListener('click', () => {
      if (!instance.pin.pinned) pin(instance);
      // A popup with popups opened from inside it stays pinned: closing it would close those too.
      else if (!open.some(other => other.pin.parent === instance)) unpin(instance);
    });
    header.append(heading, ring, closeButton);
    // The popup can be moved by its title bar. Moving pins it, so it stays where it is put.
    // The move is kept apart from the place Popper gives the popup (CSS "translate", not "transform").
    header.title = 'Drag to move';
    header.addEventListener('pointerdown', event => {
      if (event.button !== 0 || event.target.closest('button')) return;
      event.preventDefault();
      pin(instance);
      const moved = instance.pin.moved || (instance.pin.moved = { x: 0, y: 0 });
      const fromX = event.clientX - moved.x, fromY = event.clientY - moved.y;
      header.setPointerCapture(event.pointerId);
      instance.popper.classList.add('is-moved', 'is-dragging');
      const move = e => {
        moved.x = e.clientX - fromX;
        moved.y = e.clientY - fromY;
        instance.popper.style.translate = `${moved.x}px ${moved.y}px`;
      };
      const end = () => {
        instance.popper.classList.remove('is-dragging');
        header.removeEventListener('pointermove', move);
        header.removeEventListener('pointerup', end);
        header.removeEventListener('pointercancel', end);
      };
      header.addEventListener('pointermove', move);
      header.addEventListener('pointerup', end);
      header.addEventListener('pointercancel', end);
    });

    const body = document.createElement('div');
    body.className = 'reference-preview-scroll';
    body.tabIndex = 0;
    body.setAttribute('role', 'region');
    body.setAttribute('aria-label', title);
    const footer = document.createElement('div');
    footer.className = 'reference-preview-footer';
    const openLink = document.createElement('a');
    openLink.href = url.href;
    openLink.className = 'no-preview';
    openLink.textContent = 'Open full page';
    footer.append(openLink);
    shell.append(header, body, footer);
    return { shell, body, heading, footer };
  }

  async function showContent(instance, url) {
    const { shell, body, heading, footer } = previewShell(instance, url, 'Loading reference…');
    instance.pin.kids.splice(0).forEach(kid => kid.destroy());
    body.textContent = 'Loading preview…';
    instance.setContent(shell);
    try {
      const { doc, base, fetchedAt, saved } = await loadDocument(url);
      if (instance.state.isDestroyed || instance.props.content !== shell) return;
      const content = findContent(doc, url, saved);
      const titleNode = content.matches('h1, h2, h3, h4, h5, h6') ? content :
        content.querySelector('h1, h2, h3, h4, h5, h6');
      const title = content.dataset.previewTitle ||
        titleNode?.textContent.replace(/[¶#]\s*$/, '').trim() ||
        instance.reference.textContent.trim() || 'Reference preview';
      heading.textContent = title;
      body.setAttribute('aria-label', title);
      instance.popper.querySelector('.tippy-box')?.setAttribute('aria-label', `Preview: ${title}`);
      body.replaceChildren(cloneContent(content, base));
      // Links inside this popup get their own previews, with this popup as parent.
      body.querySelectorAll('a[href]').forEach(inner => {
        const kid = attach(inner, instance);
        if (kid) instance.pin.kids.push(kid);
      });
      // For js/notes.js: the reader's highlights and notes are drawn in this popup too.
      document.dispatchEvent(new CustomEvent('reference-preview:filled', {
        detail: { body, url: url.href, title, pin: () => pin(instance) },
      }));
      if (fetchedAt) {
        const source = document.createElement('span');
        source.className = 'reference-preview-source';
        source.textContent = `Saved preview · ${new Date(fetchedAt).toLocaleDateString()}`;
        footer.append(source);
      }
      // Content may contain delayed-loading images that change the panel height.
      body.querySelectorAll('img').forEach(img => {
        img.addEventListener('load', () => instance.popperInstance?.update(), { once: true });
      });
      instance.popperInstance?.update();
    } catch (_) {
      if (instance.state.isDestroyed || instance.props.content !== shell) return;
      heading.textContent = 'Preview unavailable';
      body.textContent = 'Use “Open full page” to follow this reference.';
      instance.popperInstance?.update();
    }
  }

  function attach(link, parentTip) {
    const url = targetURL(link);
    if (!url || link._tippy) return null;
    // Sphinx Design stretches a zero-height link over its card with ::after.
    // Anchor the panel to the visible card and listen across its full area.
    const card = link.matches('.sd-stretched-link, .sd-card-title a') ?
      link.closest('.sd-card') : null;
    let focusOnMount = false;
    const instance = window.tippy(link, {
      content: 'Loading preview…',
      allowHTML: false, // The custom renderer passes DOM elements.
      interactive: true,
      appendTo: () => document.body,
      theme: 'reference-preview',
      placement: 'auto',
      maxWidth: config.maxWidth,
      delay: [config.delay, 100],
      duration: [120, 80],
      // Listening for mouseleave on both the title and the card would close
      // the panel when the pointer moves from the title into the card body.
      trigger: card ? 'mouseenter' : 'mouseenter focus',
      triggerTarget: card || link,
      getReferenceClientRect: card ? () => card.getBoundingClientRect() : null,
      popperOptions: {
        modifiers: [{
          name: 'preventOverflow',
          options: { altAxis: true, padding: 16, tether: false },
        }],
      },
      touch: false,
      role: 'dialog',
      aria: { content: null, expanded: !card },
      ignoreAttributes: true,
      zIndex: 10000,
      onShow(tip) {
        if (suppressFocus) return false;
        // Opening a popup from inside another one pins the outer one.
        if (parentTip) pin(parentTip);
        // Popups that are not pinned make way; pinned ones stay.
        open.filter(other => other !== tip && !other.pin.pinned).forEach(other => closeTip(other));
        if (!open.includes(tip)) open.push(tip);
        clearTimeout(tip.pin.timer);
        tip.pin.timer = setTimeout(() => pin(tip), pinDelay);
        link.setAttribute('aria-controls', tip.popper.id);
        showContent(tip, url);
        // setContent clears this attribute when a separate trigger is used.
        link.setAttribute('aria-expanded', 'true');
      },
      onHide(tip) {
        if (tip.pin.pinned) return false; // pinned popups ignore mouse-out and clicks elsewhere
        clearTimeout(tip.pin.timer);
      },
      onMount(tip) {
        tip.popper.classList.add('reference-preview-portal');
        tip.popper.style.zIndex = String(++zTop); // newest on top
        const box = tip.popper.querySelector('.tippy-box');
        if (!box.hasAttribute('aria-label')) box.setAttribute('aria-label', 'Reference preview');
        if (focusOnMount) {
          tip.popper.querySelector('.reference-preview-scroll')?.focus();
          focusOnMount = false;
        }
      },
      onHidden(tip) {
        link.removeAttribute('aria-controls');
        link.setAttribute('aria-expanded', 'false');
        forget(tip);
        tip.pin.moved = null;                 // the next time it opens beside its link again
        tip.popper.style.translate = '';
        tip.popper.classList.remove('is-moved', 'is-dragging');
        tip.pin.kids.splice(0).forEach(kid => kid.destroy());
      },
    });
    instance.pin = { pinned: false, timer: 0, parent: parentTip, kids: [] };
    link.classList.add('has-reference-preview');
    link.setAttribute('aria-haspopup', 'dialog');
    link.setAttribute('aria-expanded', 'false');
    if (card) {
      // The visible card owns hover; its original link owns keyboard focus.
      link.addEventListener('focus', () => {
        instance.clearDelayTimeouts();
        instance.show();
      });
    }
    // Enter follows the link as usual; ArrowDown enters its interactive portal.
    link.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (instance.state.isMounted) {
          instance.popper.querySelector('.reference-preview-scroll')?.focus();
        } else {
          focusOnMount = true;
          instance.clearDelayTimeouts();
          instance.show();
        }
      }
    });
    return instance;
  }

  // The list of saved pages can also be a file that is written after the site is built
  // (config.runtimeManifest, a path inside _static). File names in it sit next to the list.
  async function loadRuntimeManifest() {
    if (!config.runtimeManifest) return;
    try {
      const manifest = new URL(config.runtimeManifest, staticBase);
      const response = await fetch(manifest, { credentials: 'same-origin', cache: 'no-cache' });
      if (!response.ok || new URL(response.url).origin !== location.origin) return;
      for (const [url, asset] of Object.entries(await response.json())) {
        if (typeof asset === 'string' && /^[\w.-]+\.json$/.test(asset)) {
          externalPages.set(externalKey(url), new URL(asset, manifest).href);
        }
      }
    } catch (_) {
      // No list (yet): links to other sites stay ordinary links.
    }
  }

  async function initialize() {
    if (typeof window.tippy !== 'function') return;
    await loadRuntimeManifest();
    document.querySelectorAll(config.parentSelector).forEach(parent => {
      parent.querySelectorAll('a[href]').forEach(link => attach(link, null));
    });
    // Esc closes the newest popup, pinned or not.
    document.addEventListener('keydown', event => {
      const tip = open[open.length - 1];
      if (event.key === 'Escape' && tip) closeTip(tip, tip.popper.contains(document.activeElement));
    });
    // A click on the page, outside every popup, closes them all.
    document.addEventListener('pointerdown', event => {
      // The buttons and boxes of js/notes.js sit outside the popups but belong to what is read in them.
      if (event.target.closest?.('.tippy-box, .user-note-ui')) return;
      open.filter(tip => !tip.pin.parent).forEach(tip => closeTip(tip));
    });
    document.addEventListener('focusin', event => {
      open.filter(tip => !tip.pin.pinned && event.target !== tip.reference &&
        !tip.popper.contains(event.target)).forEach(tip => tip.hide());
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
