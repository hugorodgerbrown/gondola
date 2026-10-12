/*
 * static/js/calendar.js — A month calendar for picking any day.
 *
 * A button marked ``data-calendar`` opens it. The button carries the day it
 * shows (``data-value``), the first and last days that can be picked
 * (``data-min``, ``data-max``) and the id of a json_script holding your own
 * plans (``data-marks``: {"2026-12-13": "skiing", …}), which draw as dots so
 * Dec and Jan can be read at a glance.
 *
 * With ``data-navigate="?from=DATE"`` picking a day goes to that address.
 * Otherwise the page attaches its own handler: ``window.dayCalendar(button,
 * onPick)``, as the map does to change day in place.
 *
 * The grid follows the WAI-ARIA date picker pattern: arrows move by a day or
 * a week, Page Up/Down by a month, Home/End to the week's ends, Enter picks,
 * Escape closes and returns focus to the button. Weeks start on Monday, and
 * a sideways swipe steps a month, as the arrows do.
 */
(function () {
  "use strict";

  const MARK_LABELS = {
    skiing: "skiing",
    not_skiing: "not skiing",
  };
  // The same strokes as templates/includes/icons/chevron-*.html.
  const CHEVRON_LEFT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>';
  const CHEVRON_RIGHT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>';
  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const monthTitle = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" });
  const longDay = new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  // Dates are handled as local midnight, built from parts, never parsed
  // from a string (which would read as UTC and slip a day east of it).
  function parse(iso) {
    if (!iso) return null;
    const parts = iso.split("-").map(Number);
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function iso(date) {
    const pad = function (n) { return String(n).padStart(2, "0"); };
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
  }

  function addDays(date, n) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate() + n);
  }

  function addMonths(date, n) {
    const first = new Date(date.getFullYear(), date.getMonth() + n, 1);
    const last = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
    return new Date(first.getFullYear(), first.getMonth(), Math.min(date.getDate(), last));
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function readMarks(id) {
    const source = id && document.getElementById(id);
    if (!source) return {};
    try {
      return JSON.parse(source.textContent) || {};
    } catch (error) {
      return {};
    }
  }

  function dayCalendar(button, onPick) {
    const min = parse(button.dataset.min);
    const max = parse(button.dataset.max);
    const today = parse(button.dataset.today) || new Date();
    const marks = readMarks(button.dataset.marks);

    const panel = el("div", "calendar");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Choose a day");
    panel.hidden = true;

    const header = el("div", "calendar__header");
    const previous = el("button", "icon-button calendar__step");
    previous.type = "button";
    previous.setAttribute("aria-label", "Previous month");
    previous.innerHTML = CHEVRON_LEFT;
    const title = el("h2", "calendar__title");
    title.setAttribute("aria-live", "polite");
    title.id = "calendar-title-" + Math.random().toString(36).slice(2);
    const next = el("button", "icon-button calendar__step");
    next.type = "button";
    next.setAttribute("aria-label", "Next month");
    next.innerHTML = CHEVRON_RIGHT;
    header.append(previous, title, next);

    const grid = el("table", "calendar__grid");
    grid.setAttribute("role", "grid");
    grid.setAttribute("aria-labelledby", title.id);
    const head = el("thead");
    const headRow = el("tr");
    WEEKDAYS.forEach(function (name) {
      const th = el("th", "calendar__weekday", name.slice(0, 2));
      th.scope = "col";
      th.setAttribute("abbr", name);
      headRow.appendChild(th);
    });
    head.appendChild(headRow);
    const body = el("tbody");
    grid.append(head, body);

    const footer = el("div", "calendar__footer");
    const todayButton = el("button", "button button--secondary calendar__today", "Today");
    todayButton.type = "button";
    const legend = el("p", "calendar__legend");
    [["skiing", "Skiing"], ["not_skiing", "Not skiing"]].forEach(function (pair) {
      const item = el("span", "calendar__key");
      item.append(el("span", "calendar__mark calendar__mark--" + pair[0]), pair[1]);
      legend.appendChild(item);
    });
    footer.append(legend, todayButton);

    panel.append(header, grid, footer);
    button.insertAdjacentElement("afterend", panel);

    let selected = parse(button.dataset.value) || today;
    let focused = selected;

    function allowed(date) {
      return !(min && date < min) && !(max && date > max);
    }

    function clamp(date) {
      if (min && date < min) return min;
      if (max && date > max) return max;
      return date;
    }

    function render(moveFocus) {
      title.textContent = monthTitle.format(focused);
      const first = new Date(focused.getFullYear(), focused.getMonth(), 1);
      // Back to the Monday on or before the 1st.
      let day = addDays(first, -((first.getDay() + 6) % 7));
      previous.disabled = Boolean(min && addDays(first, -1) < min);
      next.disabled = Boolean(max && new Date(first.getFullYear(), first.getMonth() + 1, 1) > max);
      body.replaceChildren();
      let focusTarget = null;
      for (let week = 0; week < 6; week++) {
        const row = el("tr");
        for (let weekday = 0; weekday < 7; weekday++) {
          const cell = el("td");
          const key = iso(day);
          if (day.getMonth() === focused.getMonth()) {
            const pick = el("button", "calendar__day", String(day.getDate()));
            pick.type = "button";
            pick.dataset.date = key;
            pick.tabIndex = key === iso(focused) ? 0 : -1;
            const label = [longDay.format(day)];
            if (key === iso(today)) {
              pick.classList.add("calendar__day--today");
              label.unshift("Today");
            }
            if (key === iso(selected)) {
              pick.classList.add("calendar__day--selected");
              pick.setAttribute("aria-pressed", "true");
            }
            if (marks[key]) {
              pick.appendChild(el("span", "calendar__mark calendar__mark--" + marks[key]));
              label.push(MARK_LABELS[marks[key]] || "planned");
            }
            pick.setAttribute("aria-label", label.join(", "));
            if (!allowed(day)) {
              pick.disabled = true;
            }
            if (key === iso(focused)) focusTarget = pick;
            cell.appendChild(pick);
          }
          row.appendChild(cell);
          day = addDays(day, 1);
        }
        // Drop a trailing week that holds none of this month.
        if (row.querySelector("button")) body.appendChild(row);
      }
      if (moveFocus && focusTarget) focusTarget.focus();
    }

    function moveTo(date) {
      focused = clamp(date);
      render(true);
    }

    function open() {
      selected = parse(button.dataset.value) || today;
      focused = clamp(selected);
      panel.hidden = false;
      button.setAttribute("aria-expanded", "true");
      render(true);
      document.addEventListener("pointerdown", outside, true);
    }

    function close(returnFocus) {
      panel.hidden = true;
      button.setAttribute("aria-expanded", "false");
      document.removeEventListener("pointerdown", outside, true);
      if (returnFocus) button.focus();
    }

    function outside(event) {
      if (!panel.contains(event.target) && !button.contains(event.target)) close(false);
    }

    function pick(date) {
      if (!allowed(date)) return;
      selected = date;
      button.dataset.value = iso(date);
      close(true);
      onPick(iso(date));
    }

    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", function () {
      if (panel.hidden) open(); else close(true);
    });
    function stepMonth(arrow, months) {
      if (arrow.disabled) return;
      focused = clamp(addMonths(focused, months));
      render(false);
    }
    previous.addEventListener("click", function () { stepMonth(previous, -1); });
    next.addEventListener("click", function () { stepMonth(next, 1); });
    if (window.onSwipe) {
      window.onSwipe(
        panel,
        function () { stepMonth(previous, -1); },
        function () { stepMonth(next, 1); }
      );
    }
    todayButton.addEventListener("click", function () { pick(clamp(today)); });
    body.addEventListener("click", function (event) {
      const target = event.target.closest("[data-date]");
      if (target && !target.disabled) pick(parse(target.dataset.date));
    });
    panel.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close(true);
        return;
      }
      if (!event.target.closest("[data-date]")) return;
      const weekday = (focused.getDay() + 6) % 7;
      const moves = {
        ArrowLeft: function () { return addDays(focused, -1); },
        ArrowRight: function () { return addDays(focused, 1); },
        ArrowUp: function () { return addDays(focused, -7); },
        ArrowDown: function () { return addDays(focused, 7); },
        Home: function () { return addDays(focused, -weekday); },
        End: function () { return addDays(focused, 6 - weekday); },
        PageUp: function () { return addMonths(focused, event.shiftKey ? -12 : -1); },
        PageDown: function () { return addMonths(focused, event.shiftKey ? 12 : 1); },
      };
      if (moves[event.key]) {
        event.preventDefault();
        moveTo(moves[event.key]());
      }
    });

    return {
      setValue: function (value) { button.dataset.value = value; },
      close: close,
    };
  }

  window.dayCalendar = dayCalendar;

  document.querySelectorAll("[data-calendar][data-navigate]").forEach(function (button) {
    dayCalendar(button, function (value) {
      window.location.assign(button.dataset.navigate.replace("DATE", value));
    });
  });
})();
