// Renders the chordpro lane in the browser with ChordSheetJS, plus a transpose
// control. Progressive enhancement: the server sends the raw ChordPro inside a
// readable <pre>, and this script -- only if it and the vendored library both
// load -- replaces it with the formatted chord sheet. With JavaScript off, or if
// parsing throws, the <pre> stays and the page is still usable.
//
// Our own asset (not vendored): served from /static/js/, same origin as the page.
(function () {
  "use strict";

  var root = document.getElementById("artifact");
  if (!root || !window.ChordSheetJS) return;

  var source = root.querySelector("pre.source");
  var target = root.querySelector(".chord-sheet-render");
  var control = root.querySelector(".transpose");
  var amountEl = root.querySelector(".transpose-amount");
  if (!source || !target) return;

  var song;
  try {
    song = new ChordSheetJS.ChordProParser().parse(source.textContent);
  } catch (err) {
    // Leave the <pre> visible -- a readable tab beats a blank panel.
    return;
  }

  var formatter = new ChordSheetJS.HtmlDivFormatter();
  var amount = 0;

  function render() {
    var shown = amount === 0 ? song : song.transpose(amount);
    target.innerHTML = formatter.format(shown);
    // The page already prints title/artist/meta from meta.yaml; drop the copy
    // the formatter emits so it is not shown twice.
    target.querySelectorAll(".title, .subtitle").forEach(function (el) {
      el.remove();
    });
    if (amountEl) amountEl.textContent = (amount > 0 ? "+" : "") + amount;
  }

  render();
  source.hidden = true;

  if (control) {
    control.hidden = false;
    control.addEventListener("click", function (ev) {
      var button = ev.target.closest("[data-transpose]");
      if (!button) return;
      amount += parseInt(button.getAttribute("data-transpose"), 10);
      render();
    });
  }
})();
