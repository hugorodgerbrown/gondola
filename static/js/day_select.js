/*
 * static/js/day_select.js — Select several days on My days and plan them at once.
 *
 * A tap opens one day, as before. Pressing and holding a day (or, with a
 * mouse, dragging from one day onto another) starts selecting, as in the
 * Photos app: ticked days, and a bar above the tabs that counts them. While
 * selecting, a tap adds or removes a day, and a hold-and-drag sweeps a run
 * (starting on a ticked day sweeps them off instead). "Plan" opens one
 * sheet for every ticked day. The selection survives stepping to another
 * month, so a trip can cross the end of one, and is forgotten once saved.
 * It belongs to the person signed in, and stops at the most days one
 * sheet can plan.
 */
(function () {
  "use strict";

  const grid = document.querySelector("[data-select-days]");
  const bar = document.querySelector("[data-select-bar]");
  if (!grid || !bar) {
    return;
  }

  const KEY = "my-days-selection";
  const HOLD_MS = 400;
  const MOVE_PX = 10;
  const MAX = Number(grid.dataset.selectMax) || 62;
  const count = bar.querySelector("[data-select-count]");
  const plan = bar.querySelector("[data-select-plan]");
  let selected = new Set();
  let selecting = false;
  let press = null;
  // The click that ends a hold or a sweep lands, a moment later, on the
  // day it ended on; that one click isn't a tap.
  let swallow = null;

  function cells() {
    return grid.querySelectorAll("a.mday[data-date]");
  }

  function cellAt(x, y) {
    const element = document.elementFromPoint(x, y);
    return element ? element.closest("a.mday[data-date]") : null;
  }

  function save() {
    try {
      if (selecting) {
        sessionStorage.setItem(
          KEY,
          JSON.stringify({ owner: grid.dataset.selectOwner, days: Array.from(selected) })
        );
      } else {
        sessionStorage.removeItem(KEY);
      }
    } catch (error) {
      // Private browsing: the selection just won't outlast the page.
    }
  }

  function render() {
    grid.classList.toggle("month--selecting", selecting);
    cells().forEach(function (cell) {
      const on = selected.has(cell.dataset.date);
      cell.classList.toggle("mday--picked", on);
      if (selecting) {
        cell.setAttribute("aria-pressed", on ? "true" : "false");
      } else {
        cell.removeAttribute("aria-pressed");
      }
    });
    bar.hidden = !selecting;
    document.body.classList.toggle("has-select-bar", selecting);
    const n = selected.size;
    count.textContent =
      n === 0 ? "Tap days to select" :
      n === 1 ? "1 day" :
      n >= MAX ? n + " days, the most" :
      n + " days";
    plan.disabled = n === 0;
  }

  function begin() {
    selecting = true;
    if (navigator.vibrate) {
      navigator.vibrate(10);
    }
  }

  function finish() {
    selecting = false;
    selected = new Set();
    save();
    render();
  }

  // The days from the press to the pointer, inclusive, as ISO dates.
  function run() {
    const a = press.startCell.dataset.date;
    const b = press.endCell.dataset.date;
    const first = a <= b ? a : b;
    const last = a <= b ? b : a;
    return Array.from(cells())
      .map(function (cell) { return cell.dataset.date; })
      .filter(function (date) { return date >= first && date <= last; });
  }

  function sweep() {
    selected = new Set(press.base);
    run().forEach(function (date) {
      if (!press.adding) {
        selected.delete(date);
      } else if (selected.size < MAX) {
        selected.add(date);
      }
    });
    render();
  }

  function activate() {
    press.active = true;
    if (!selecting) {
      begin();
    }
    sweep();
  }

  function reset() {
    if (press && press.timer) {
      clearTimeout(press.timer);
    }
    press = null;
  }

  grid.addEventListener("pointerdown", function (event) {
    swallow = null; // a new press: whatever click was owed never came
    const cell = event.target.closest("a.mday[data-date]");
    if (!event.isPrimary || !cell || (event.pointerType === "mouse" && event.button !== 0)) {
      return;
    }
    press = {
      startCell: cell,
      endCell: cell,
      x: event.clientX,
      y: event.clientY,
      type: event.pointerType,
      base: new Set(selected),
      adding: !selected.has(cell.dataset.date),
      active: false,
      timer: null,
    };
    if (press.type !== "mouse") {
      press.timer = setTimeout(activate, HOLD_MS);
    }
  });

  grid.addEventListener("pointermove", function (event) {
    if (!press || !event.isPrimary) {
      return;
    }
    const cell = cellAt(event.clientX, event.clientY);
    if (!press.active) {
      if (press.type === "mouse") {
        if (cell && cell !== press.startCell) {
          press.endCell = cell;
          activate();
        }
      } else if (Math.hypot(event.clientX - press.x, event.clientY - press.y) > MOVE_PX) {
        reset(); // a swipe or a scroll, not a selection
      }
      return;
    }
    if (cell && cell !== press.endCell) {
      press.endCell = cell;
      sweep();
    }
  });

  grid.addEventListener("pointerup", function (event) {
    if (!press || !event.isPrimary) {
      return;
    }
    if (press.active) {
      // The click that ends a hold or a sweep isn't a tap.
      swallow = { cell: press.endCell, until: Date.now() + 800 };
      save();
    }
    reset();
  });

  grid.addEventListener("pointercancel", reset);

  // Once sweeping, a finger moving up or down selects rather than scrolls.
  grid.addEventListener("touchmove", function (event) {
    if (press && press.active && event.cancelable) {
      event.preventDefault();
    }
  }, { passive: false });

  grid.addEventListener("contextmenu", function (event) {
    if (event.target.closest("a.mday[data-date]")) {
      event.preventDefault();
    }
  });

  grid.addEventListener("dragstart", function (event) {
    event.preventDefault();
  });

  // While selecting, a tap ticks a day instead of opening it.
  grid.addEventListener("click", function (event) {
    const cell = event.target.closest("a.mday[data-date]");
    const ending = Boolean(swallow && swallow.cell === cell && Date.now() < swallow.until);
    swallow = null;
    if (ending || (selecting && cell)) {
      event.preventDefault();
      event.stopPropagation();
    }
    if (ending || !selecting || !cell) {
      return;
    }
    const date = cell.dataset.date;
    if (selected.has(date)) {
      selected.delete(date);
    } else if (selected.size < MAX) {
      selected.add(date);
    }
    save();
    render();
  }, true);

  bar.querySelector("[data-select-cancel]").addEventListener("click", finish);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && selecting && !document.querySelector("dialog[open]")) {
      finish();
    }
  });

  plan.addEventListener("click", function () {
    if (selected.size === 0) {
      return;
    }
    let url = grid.dataset.selectDays + "?days=" + Array.from(selected).sort().join(",");
    if (grid.dataset.selectFrom) {
      url += "&from=" + grid.dataset.selectFrom;
    }
    htmx.ajax("GET", url, { target: "#sheet-body" });
  });

  // Saved or cleared: the page reloads, and the selection is done with.
  document.body.addEventListener("htmx:beforeOnLoad", function (event) {
    const xhr = event.detail.xhr;
    if (
      selecting &&
      event.detail.requestConfig.verb === "post" &&
      event.detail.pathInfo.requestPath.indexOf(grid.dataset.selectDays) === 0 &&
      xhr.getResponseHeader("HX-Refresh")
    ) {
      selecting = false;
      save();
    }
  });

  // Not a swipe to the next month while sweeping.
  grid.isPicking = function () {
    return Boolean(press && press.active);
  };

  try {
    // Only the person who made it, and only days that can still be planned:
    // someone else may sign in on this tab, or the selection may be from
    // yesterday.
    const stored = JSON.parse(sessionStorage.getItem(KEY) || "null");
    if (stored && stored.owner === grid.dataset.selectOwner && Array.isArray(stored.days)) {
      selecting = true;
      selected = new Set(
        stored.days.filter(function (date) { return date >= grid.dataset.today; }).slice(0, MAX)
      );
    }
  } catch (error) {
    // Nothing stored, or nothing readable: start without a selection.
  }
  render();
})();
