/*
 * The "Contents" list on the right: marks the part of the page that is being read, and
 * lets a long name go on to a second line in a place that reads well.
 *
 * The theme is meant to do this itself, but its two packages do not fit together here.
 * The page template of sphinx-book-theme 1.2.0 leaves out the class name (bd-toc-nav)
 * under which the script of pydata-sphinx-theme 0.16.1 looks for the list. Bootstrap's
 * "scroll spy" then takes every link of the page instead, and it stops with an error at
 * an id that has brackets in it, such as the id of an overloaded method. It could not
 * follow the code reference in any case: it looks ids up as CSS selectors, and the ids
 * there contain full stops.
 *
 * So the scroll spy is switched off here, and this file does its work with
 * getElementById. The theme's own styles do the rest: a marked link is coloured, and the
 * list below a marked entry opens. That is the only way the members of a type become
 * visible in the list.
 */
(() => {
  'use strict';

  // This file is loaded with "defer", so it runs before the page's "load" event. That is
  // when Bootstrap would start its scroll spy on an element that has this attribute.
  document.body.removeAttribute('data-bs-spy');

  const nav = document.getElementById('pst-page-toc-nav');
  if (!nav) return;

  // The list is narrow, and a long name needs two lines. Without help the browser divides it
  // wherever the line is full: "IsJurisdictionMatch(" and ")". A <wbr> element marks a place
  // where it may divide instead: after a full stop, and before a capital letter that follows
  // a small letter or a digit. That gives "IsJurisdiction" and "Match()".
  for (const word of nav.querySelectorAll('span.pre')) {
    const parts = word.textContent.replace(/\.(?=\w)|[a-z0-9](?=[A-Z])/g, '$&\n').split('\n');
    if (parts.length < 2) continue;
    word.replaceChildren(...parts.flatMap((part, index) => (index ? [document.createElement('wbr'), part] : [part])));
  }

  // One entry for every link of the list that points at something on this page, top to bottom.
  const entries = [];
  for (const link of nav.querySelectorAll('a[href^="#"]')) {
    const target = byId(link.getAttribute('href'));
    if (target) entries.push({ link, target });
  }
  if (!entries.length) return;

  function byId(hash) {
    try {
      return document.getElementById(decodeURIComponent(hash.slice(1)));
    } catch (error) {
      return null;   // a "%" that is not part of an encoded character
    }
  }

  // The entry that is being read: the first heading below the bar at the top of the window
  // when it stands in the upper half of the window, and otherwise the heading before it.
  function entryBeingRead() {
    const bar = document.querySelector('.bd-header-article');
    const top = bar ? Math.max(bar.getBoundingClientRect().bottom, 0) : 0;
    const middle = top + (window.innerHeight - top) / 2;
    let before = null;
    for (const entry of entries) {
      if (!entry.target.getClientRects().length) continue;   // not shown on the page
      const at = entry.target.getBoundingClientRect().top;
      if (at >= top - 1) return at < middle ? entry : before;
      before = entry;
    }
    return before;   // every heading is above the window: the last one
  }

  let current;   // the entry that is marked now
  function show(entry) {
    if (entry === current) return;
    current = entry;
    for (const marked of nav.querySelectorAll('.active, [aria-current]')) {
      marked.classList.remove('active');
      marked.removeAttribute('aria-current');
    }
    if (!entry) return;
    // The entry itself and the entries it is listed under.
    for (let item = entry.link.parentElement; item && nav.contains(item); item = item.parentElement.closest('li')) {
      item.classList.add('active');
      item.querySelector(':scope > a')?.classList.add('active');
    }
    entry.link.setAttribute('aria-current', 'location');
    keepInSight(entry.link);
  }

  // The list has a scroll bar of its own when it is longer than the window.
  function keepInSight(link) {
    const box = nav.closest('.bd-sidebar-secondary');
    if (!box || !link.getClientRects().length) return;
    const frame = box.getBoundingClientRect();
    const row = link.getBoundingClientRect();
    const edge = 12;
    if (row.top < frame.top + edge) box.scrollTop -= frame.top + edge - row.top;
    else if (row.bottom > frame.bottom - edge) box.scrollTop += row.bottom - (frame.bottom - edge);
  }

  let waiting = false;
  function later() {   // at most once for every frame the browser draws
    if (waiting) return;
    waiting = true;
    requestAnimationFrame(() => {
      waiting = false;
      if (!chosen) show(entryBeingRead());
    });
  }

  // A reader who picks an entry, or follows a link to one, gets that entry marked, also
  // when the page cannot scroll far enough to bring it to the top of the window. The mark
  // stays while the page moves there, and gives way the next time the reader scrolls.
  let chosen = false;
  let rest = 0;
  function choose(entry) {
    show(entry);
    chosen = true;
    stillMoving();
  }
  function stillMoving() {
    clearTimeout(rest);
    rest = setTimeout(() => { chosen = false; }, 200);
  }

  // The entry for the place named in the address (page.html#place), or the nearest entry
  // that place is part of.
  function fromAddress() {
    const place = location.hash.length > 1 ? byId(location.hash) : null;
    return place ? entries.filter(entry => entry.target.contains(place)).pop() : undefined;
  }

  function start() {
    const entry = fromAddress();
    if (entry) choose(entry);
    else show(entryBeingRead());
  }

  nav.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;   // opens elsewhere
    const link = event.target.closest('a');
    const entry = entries.find(candidate => candidate.link === link);
    if (entry) choose(entry);
  });
  window.addEventListener('hashchange', () => {
    const entry = fromAddress();
    if (entry) choose(entry);
    else later();
  });
  window.addEventListener('scroll', () => {
    if (chosen) stillMoving();
    else later();
  }, { passive: true });
  window.addEventListener('resize', later);
  window.addEventListener('load', start);   // pictures and fonts have moved things by then
  start();
})();
