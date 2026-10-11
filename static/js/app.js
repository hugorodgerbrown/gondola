/*
 * static/js/app.js — The little behaviour every page shares.
 *
 * Opens the bottom sheet when HTMX swaps a fragment into it, closes it on
 * a close button or a tap on the backdrop, and wires share buttons to the
 * phone's share sheet (falling back to copying the link). Before a sign-out
 * (or account deletion) form posts, drops the pages the service worker
 * cached, so the next person on this device can't open them offline. In
 * a day sheet over several days, changing an answer that differed across
 * them drops its "keep as is" flag. The
 * signed-out front page drops them again, which covers a sign-out posted
 * from a page loaded before this script had the handler. ``onSwipe`` turns
 * a sideways swipe into "previous" or "next", for the month calendars.
 */
(function () {
  "use strict";

  const sheet = document.getElementById("sheet");

  function closeSheet() {
    if (sheet && sheet.open) {
      sheet.close();
    }
  }

  document.body.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail.target && event.detail.target.id === "sheet-body") {
      if (!sheet.open) {
        sheet.showModal();
      }
      const focusable = sheet.querySelector("[autofocus]");
      if (focusable) {
        focusable.focus();
      }
      document.dispatchEvent(new CustomEvent("sheet:opened", { detail: sheet }));
    }
  });

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-close-sheet]")) {
      event.preventDefault();
      if (sheet && sheet.open) {
        closeSheet();
      } else {
        // The sheet was opened as a page of its own.
        history.length > 1 ? history.back() : (location.href = "/");
      }
    }
  });

  // Day sheet over several days: a note or privacy that differs across
  // them is kept unless changed. Changing it drops the "keep" flag.
  function dropKeep(event) {
    const form = event.target.closest("[data-day-form]");
    if (!form || !event.target.name) {
      return;
    }
    const keep = form.querySelector('[data-keep-for="' + event.target.name + '"]');
    if (keep) {
      keep.remove();
    }
  }

  document.addEventListener("input", dropKeep);
  document.addEventListener("change", dropKeep);

  // A resort list where nothing picked means no resort: tapping the picked
  // resort again clears it. "Leave as it is" stays a plain radio.
  function clearableRadio(event) {
    const choice = event.target.closest("[data-clearable] .choice");
    const radio = choice && choice.querySelector("input[type=radio]");
    return radio && radio.value !== "keep" ? radio : null;
  }

  document.addEventListener("pointerdown", function (event) {
    const radio = clearableRadio(event);
    if (radio) {
      radio.dataset.wasChecked = radio.checked ? "1" : "";
    }
  });

  document.addEventListener("click", function (event) {
    const radio = clearableRadio(event);
    if (!radio || event.target !== radio) {
      return; // A click on the label arrives again on the radio itself.
    }
    if (radio.dataset.wasChecked) {
      radio.checked = false;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
    }
    radio.dataset.wasChecked = "";
  });

  document.addEventListener("htmx:afterSwap", function (event) {
    const target = event.detail.target;
    if (target && target.id === "resort-results") {
      target.hidden = target.innerHTML.trim() === "";
    }
  });

  if (sheet) {
    // A click on the dialog itself (not its contents) is the backdrop.
    sheet.addEventListener("click", function (event) {
      if (event.target === sheet) {
        closeSheet();
      }
    });
    sheet.addEventListener("close", function () {
      document.getElementById("sheet-body").innerHTML = "";
      document.dispatchEvent(new CustomEvent("sheet:closed"));
    });
  }

  document.addEventListener("click", async function (event) {
    const button = event.target.closest("[data-share-url]");
    if (!button) {
      return;
    }
    event.preventDefault();
    const url = button.dataset.shareUrl;
    const title = button.dataset.shareTitle || document.title;
    if (navigator.share) {
      try {
        await navigator.share({ title: title, url: url });
        return;
      } catch (error) {
        if (error && error.name === "AbortError") {
          return;
        }
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      const label = button.textContent;
      button.textContent = button.dataset.copiedLabel || "Link copied";
      setTimeout(function () {
        button.textContent = label;
      }, 2000);
    } catch (error) {
      window.prompt("Copy this link", url);
    }
  });

  async function forgetPages() {
    if (!window.caches) {
      return;
    }
    const names = await caches.keys();
    await Promise.all(names.filter(function (name) {
      return name.startsWith("pages-");
    }).map(function (name) {
      return caches.delete(name);
    }));
  }

  document.addEventListener("submit", function (event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-sign-out")) {
      return;
    }
    if (form.dataset.cleared) {
      return;
    }
    event.preventDefault();
    function submit() {
      form.dataset.cleared = "1";
      form.submit();
    }
    // Sign out whether or not the cleanup worked.
    forgetPages().then(submit, submit);
  });

  // Only with signal: offline, this page may be an old copy from the cache.
  if (document.querySelector("[data-forget-pages]") && navigator.onLine) {
    forgetPages().catch(function () {});
  }

  // A sideways swipe on ``element``: onNext for right-to-left, onPrevious
  // for left-to-right. Mostly-vertical moves are left to scrolling, and the
  // click a mouse drag would end in is swallowed.
  const SWIPE_MIN_PX = 48;
  const SWIPE_MAX_MS = 800;

  function onSwipe(element, onPrevious, onNext) {
    let start = null;
    let swiped = false;
    element.style.touchAction = "pan-y";
    element.addEventListener("pointerdown", function (event) {
      if (event.isPrimary) start = { x: event.clientX, y: event.clientY, t: event.timeStamp };
    });
    element.addEventListener("pointercancel", function () { start = null; });
    // A mouse drag on a day's link would start dragging the link instead.
    element.addEventListener("dragstart", function (event) { event.preventDefault(); });
    element.addEventListener("pointerup", function (event) {
      if (!start || !event.isPrimary) return;
      // My days: a drag that is picking a run of days isn't a swipe.
      if (element.isPicking && element.isPicking()) {
        start = null;
        return;
      }
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      const quick = event.timeStamp - start.t < SWIPE_MAX_MS;
      start = null;
      if (!quick || Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      // A click, if any, follows straight after; it isn't a tap on a day.
      swiped = true;
      setTimeout(function () { swiped = false; }, 0);
      (dx < 0 ? onNext : onPrevious)();
    });
    element.addEventListener("click", function (event) {
      if (swiped) {
        event.preventDefault();
        event.stopPropagation();
      }
    }, true);
  }
  window.onSwipe = onSwipe;

  // My days: swipe between months, as the arrows do.
  document.querySelectorAll("[data-swipe-previous], [data-swipe-next]").forEach(function (element) {
    function go(url) {
      if (url) location.href = url;
    }
    onSwipe(
      element,
      function () { go(element.dataset.swipePrevious); },
      function () { go(element.dataset.swipeNext); }
    );
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
})();
