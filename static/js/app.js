/*
 * static/js/app.js — The little behaviour every page shares.
 *
 * Opens the bottom sheet when HTMX swaps a fragment into it, closes it on
 * a close button or a tap on the backdrop, and wires share buttons to the
 * phone's share sheet (falling back to copying the link). ``onSwipe`` turns
 * a sideways swipe into "previous" or "next", for the month calendars.
 * An open "…" row menu closes on a tap anywhere else. The service worker,
 * the offline banner and clearing cached pages at sign-out are pwa.js's;
 * this file only retires Gondola's first worker (``retireRootWorker``).
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

  document.addEventListener("click", function (event) {
    document.querySelectorAll("details.row-menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) {
        menu.open = false;
      }
    });
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
    const text = button.dataset.shareText;
    if (navigator.share) {
      try {
        await navigator.share(text ? { title: title, text: text, url: url } : { title: title, url: url });
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
      // Calendar: a drag that is picking a run of days isn't a swipe.
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

  // Calendar: swipe between months, as the arrows do.
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

  // Gondola's first service worker was registered at /sw.js for the whole
  // site, with its own caches. A phone that installed it still has both:
  // unregister it and drop them, so it can never again answer for a page,
  // signed out or not. The app's worker is /app/sw.js, scoped to /app/.
  var ROOT_CACHES = ["static-v1", "pages-v1"];
  function retireRootWorker() {
    var jobs = [];
    if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
      jobs.push(navigator.serviceWorker.getRegistrations().then(function (registrations) {
        var root = location.origin + "/";
        return Promise.all(registrations.filter(function (registration) {
          return registration.scope === root;
        }).map(function (registration) { return registration.unregister(); }));
      }));
    }
    if (window.caches) {
      jobs.push(Promise.all(ROOT_CACHES.map(function (name) { return caches.delete(name); })));
    }
    return Promise.all(jobs).catch(function () { /* nothing to retire */ });
  }
  window.retireRootWorker = retireRootWorker;
  retireRootWorker();
})();
