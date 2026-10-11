/*
 * static/js/app.js — The little behaviour every page shares.
 *
 * Opens the bottom sheet when HTMX swaps a fragment into it, closes it on
 * a close button or a tap on the backdrop, and wires share buttons to the
 * phone's share sheet (falling back to copying the link). Before a sign-out
 * (or account deletion) form posts, drops the pages the service worker
 * cached, so the next person on this device can't open them offline.
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

  // Day sheet: the resort picker only matters when the day is "Skiing".
  function syncResortPicker(form) {
    const picker = form.querySelector("[data-resort-picker]");
    const checked = form.querySelector("[data-status]:checked");
    if (picker && checked) {
      picker.hidden = checked.value !== "resort";
    }
  }

  document.addEventListener("change", function (event) {
    const form = event.target.closest("[data-day-form]");
    if (form && event.target.matches("[data-status]")) {
      syncResortPicker(form);
    }
  });

  document.addEventListener("htmx:afterSwap", function (event) {
    const target = event.detail.target;
    if (target && target.id === "resort-results") {
      target.hidden = target.innerHTML.trim() === "";
    }
    document.querySelectorAll("[data-day-form]").forEach(syncResortPicker);
  });

  document.querySelectorAll("[data-day-form]").forEach(syncResortPicker);

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

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
})();
