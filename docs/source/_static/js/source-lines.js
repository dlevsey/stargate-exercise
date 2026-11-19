/* Pages of the dev docs that show a repository file.

   A link such as Program.cs.html#L6-L21 means "lines 6 to 21 of this file". The browser does
   not know that, so this script marks those lines and scrolls to the first one. Every line of
   such a page is a <span id="L-6"> (written by the source-listing directive). */
(function () {
  'use strict';

  var marked = [];

  function show() {
    var match = /^#L(\d+)(?:-L?(\d+))?$/.exec(window.location.hash);
    marked.forEach(function (line) { line.classList.remove('hll', 'source-line-marked'); });
    marked = [];
    if (!match) return;
    var first = Number(match[1]);
    var last = Math.max(first, Number(match[2] || match[1]));
    for (var number = first; number <= last; number += 1) {
      var line = document.getElementById('L-' + number);
      if (!line) break;
      line.classList.add('hll', 'source-line-marked');
      marked.push(line);
    }
    if (marked.length) marked[0].scrollIntoView({ block: 'center' });
  }

  if (!document.querySelector('.source-listing')) return;
  window.addEventListener('hashchange', show);
  if (document.readyState === 'complete') show();
  else window.addEventListener('load', show);
})();
