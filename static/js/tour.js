/*
 * static/js/tour.js — Play the onboarding tour over the real screens.
 *
 * The server writes the chapters played on this page into #tour-script
 * (apps/tour/context_processors.py) only while the person is touring a
 * demo group. Each frame is a coach mark: a page intro is a card over the
 * dimmed page; a zoom-in dims everything but its target and moves on with
 * Next; a tap frame moves on only when the person taps the real control,
 * which leads to the next page (or opens a sheet, whose frames follow).
 *
 * The dimming is four panels round a hole, so whatever is in the hole can
 * be tapped and nothing else can. While a sheet is open the layer moves
 * inside it, since a modal dialog sits above the rest of the page. The
 * frame reached is kept per page in sessionStorage, so a reload (a resort
 * chip tapped in chapter 1) resumes where it was.
 *
 * Saving is stopped on the server (apps/tour/middleware.py), not here.
 * After the tour, the hand-off card (chapter 7) only needs closing.
 */
(function () {
  "use strict";

  // Chapter 7: the hand-off over the real My days closes on Later or Let's go.
  document.querySelectorAll("[data-tour-handoff]").forEach(function (layer) {
    layer.addEventListener("click", function (event) {
      if (event.target.closest("[data-tour-close]")) layer.remove();
    });
    const first = layer.querySelector("button, a");
    if (first) first.focus();
  });

  const source = document.getElementById("tour-script");
  if (!source) return;
  let script;
  try {
    script = JSON.parse(source.textContent);
  } catch (error) {
    return;
  }

  const frames = [];
  script.chapters.forEach(function (chapter) {
    chapter.frames.forEach(function (frame, index) {
      frames.push({ chapter: chapter, frame: frame, step: index, steps: chapter.frames.length });
    });
  });
  const bar = document.querySelector("[data-tour-bar]");
  const chapterInput = bar && bar.querySelector("[data-tour-chapter]");
  if (!frames.length) return;

  // The map opens on the day's busy pins, not wherever it was last left.
  if (script.page === "map") {
    try { sessionStorage.removeItem("resort-map-view"); } catch (error) { /* no storage */ }
  }

  const KEY = "tour-at:" + script.page;
  const PAD = 6;
  const WAIT_MS = 5000;
  const sheet = document.getElementById("sheet");

  function remembered() {
    let at = 0;
    try { at = parseInt(sessionStorage.getItem(KEY), 10) || 0; } catch (error) { /* no storage */ }
    if (at < 0 || at >= frames.length) return 0;
    // A frame in a sheet that a reload closed: go back to the tap that opens it.
    return inSheet(at) ? tapBefore(at) : at;
  }

  // The tap frame before ``index``: the one that opened its sheet.
  function tapBefore(index) {
    let back = index - 1;
    while (back > 0 && !frames[back].frame.tap) back -= 1;
    return Math.max(0, back);
  }

  function remember(at) {
    try { sessionStorage.setItem(KEY, String(at)); } catch (error) { /* no storage */ }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  // The layer: four shades round the hole, a ring on its edge, the card.
  const layer = el("div", "tour-layer");
  const shades = ["top", "right", "bottom", "left"].map(function (side) {
    const shade = el("div", "tour-shade tour-shade--" + side);
    layer.appendChild(shade);
    return shade;
  });
  const ring = el("div", "tour-ring");
  layer.appendChild(ring);
  const card = el("section", "tour-card");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-live", "polite");
  const eyebrow = el("span", "eyebrow");
  const title = el("h2", "title tour-card__title");
  const text = el("p", "tour-card__text");
  const note = el("p", "small muted tour-card__note");
  const actions = el("div", "tour-card__actions");
  const count = el("span", "small muted tour-card__count");
  const next = el("button", "button button--small", "Next");
  next.type = "button";
  actions.append(count, next);
  card.append(eyebrow, title, text, note, actions);
  layer.appendChild(card);

  let at = remembered();
  let targets = [];
  let raf = 0;
  let waiting = 0;

  function host() {
    return sheet && sheet.open ? sheet : document.body;
  }

  function find(selectors) {
    return selectors.map(function (selector) {
      return document.querySelector(selector);
    }).filter(Boolean);
  }

  function union(nodes) {
    let top = Infinity, left = Infinity, right = -Infinity, bottom = -Infinity;
    nodes.forEach(function (node) {
      const rect = node.getBoundingClientRect();
      top = Math.min(top, rect.top);
      left = Math.min(left, rect.left);
      right = Math.max(right, rect.right);
      bottom = Math.max(bottom, rect.bottom);
    });
    return { top: top - PAD, left: left - PAD, right: right + PAD, bottom: bottom + PAD };
  }

  function place() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    let hole = { top: height / 2, left: width / 2, right: width / 2, bottom: height / 2 };
    const live = targets.filter(function (node) { return node.isConnected; });
    if (live.length) hole = union(live);
    const top = Math.max(0, hole.top), bottom = Math.min(height, hole.bottom);
    const left = Math.max(0, hole.left), right = Math.min(width, hole.right);
    Object.assign(shades[0].style, { top: "0", left: "0", width: "100%", height: top + "px" });
    Object.assign(shades[2].style, { top: bottom + "px", left: "0", width: "100%", height: Math.max(0, height - bottom) + "px" });
    Object.assign(shades[3].style, { top: top + "px", left: "0", width: left + "px", height: Math.max(0, bottom - top) + "px" });
    Object.assign(shades[1].style, { top: top + "px", left: right + "px", width: Math.max(0, width - right) + "px", height: Math.max(0, bottom - top) + "px" });
    ring.hidden = !live.length;
    Object.assign(ring.style, { top: hole.top + "px", left: hole.left + "px", width: (hole.right - hole.left) + "px", height: (hole.bottom - hole.top) + "px" });
    // The card sits below the hole when it fits, else above, else centred.
    card.classList.toggle("tour-card--centred", !live.length);
    if (live.length) {
      const room = card.offsetHeight + 16;
      let y;
      if (hole.bottom + room < height - 72) y = hole.bottom + 12;
      else if (hole.top - room > 0) y = hole.top - room + 4;
      else y = Math.max(12, height - room - 72);
      card.style.top = y + "px";
    } else {
      card.style.top = "";
    }
    raf = requestAnimationFrame(place);
  }

  function hide() {
    cancelAnimationFrame(raf);
    clearTimeout(waiting);
    layer.remove();
  }

  function show(index) {
    hide();
    at = index;
    remember(at);
    const item = frames[at];
    const frame = item.frame;
    if (chapterInput) chapterInput.value = String(item.chapter.number);
    const intro = frame.target.length === 0;
    eyebrow.textContent = intro ? "Chapter " + item.chapter.number : item.chapter.name;
    title.textContent = item.chapter.name;
    title.hidden = !intro;
    text.textContent = frame.text;
    note.textContent = frame.note;
    note.hidden = !frame.note;
    count.textContent = (item.step + 1) + " of " + item.steps;
    next.hidden = Boolean(frame.tap);
    next.textContent = frame.finish ? "Finish" : "Next";
    targets = [];
    if (intro) {
      render();
      return;
    }
    const started = Date.now();
    (function look() {
      const found = find(frame.target);
      if (found.length === frame.target.length || (found.length && Date.now() - started > 1000)) {
        targets = found;
        // A tap frame keeps the control to tap in view; others their target.
        const anchor = (frame.tap && document.querySelector(frame.tap)) || found[0];
        anchor.scrollIntoView({ block: "center", inline: "nearest" });
        render();
      } else if (Date.now() - started > WAIT_MS) {
        // Nothing to point at (a day in next month): a tap frame still
        // shows, centred, with Next; a zoom-in is skipped.
        if (frame.tap) {
          next.hidden = false;
          render();
        } else {
          advance();
        }
      } else {
        waiting = setTimeout(look, 100);
      }
    })();
  }

  function render() {
    host().appendChild(layer);
    place();
    if (!next.hidden) next.focus({ preventScroll: true });
  }

  function advance() {
    const frame = frames[at].frame;
    if (frame.finish) {
      hide();
      try { sessionStorage.removeItem(KEY); } catch (error) { /* no storage */ }
      const form = document.querySelector("[data-tour-finish]");
      if (form) form.submit();
      return;
    }
    if (at + 1 < frames.length) show(at + 1);
    else hide();
  }

  next.addEventListener("click", advance);

  // A tap frame moves on when its control is tapped. The tap goes on to do
  // what it does (a link, a sheet, a form the server answers).
  document.addEventListener("click", function (event) {
    const frame = frames[at] && frames[at].frame;
    if (!frame || !frame.tap || !layer.isConnected) return;
    if (!event.target.closest(frame.tap)) return;
    hide();
    if (at + 1 < frames.length) {
      // The next frame is on this page, once the sheet it opens arrives.
      remember(at + 1);
      show(at + 1);
    } else {
      try { sessionStorage.removeItem(KEY); } catch (error) { /* no storage */ }
    }
  }, true);

  // A frame in a sheet: a later chapter on this page, or one pointing in.
  function inSheet(index) {
    const item = frames[index];
    return item.chapter.number !== frames[0].chapter.number ||
      item.frame.target.some(function (selector) { return selector.indexOf("#sheet") === 0; });
  }

  // A sheet closed mid-chapter goes back to the tap that opened it.
  document.addEventListener("sheet:closed", function () {
    if (!frames[at] || !inSheet(at)) return;
    show(tapBefore(at));
  });

  // The layer follows the sheet into the top layer, and back out.
  document.addEventListener("sheet:opened", function () {
    if (layer.isConnected && layer.parentNode !== host()) host().appendChild(layer);
  });

  show(at);
})();
