/*
 * static/js/map.js — Every map in the app: the resort map, the meeting-pin
 * picker on the meet-up form, and the small map on a meet-up page.
 *
 * The basemap is MAP_STYLE_URL (swisstopo's winter map by default). If it can't be
 * fetched (no signal, blocked host) the map draws a plain ground with
 * Switzerland's outline instead, so the pins still make sense.
 * Pins are HTML markers, so they draw without a font server.
 */
(function () {
  "use strict";

  const SWITZERLAND = [[5.9, 45.8], [10.5, 47.85]];
  const STYLE_TIMEOUT_MS = 4000;

  function fallbackStyle(outlineUrl) {
    return {
      version: 8,
      sources: { ch: { type: "geojson", data: outlineUrl } },
      layers: [
        { id: "ground", type: "background", paint: { "background-color": "#e9e7e1" } },
        { id: "ch-fill", type: "fill", source: "ch", paint: { "fill-color": "#f7f5f0" } },
        {
          id: "ch-line",
          type: "line",
          source: "ch",
          paint: { "line-color": "rgba(0,0,0,0.25)", "line-width": 1.2 },
        },
      ],
    };
  }

  async function loadStyle(url, outlineUrl) {
    if (!url) {
      return fallbackStyle(outlineUrl);
    }
    const controller = new AbortController();
    const timer = setTimeout(function () {
      controller.abort();
    }, STYLE_TIMEOUT_MS);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) {
        throw new Error("style " + response.status);
      }
      return await response.json();
    } catch (error) {
      return fallbackStyle(outlineUrl);
    } finally {
      clearTimeout(timer);
    }
  }

  async function createMap(container, options) {
    const style = await loadStyle(container.dataset.styleUrl, container.dataset.outlineUrl);
    const map = new maplibregl.Map(
      Object.assign(
        {
          container: container,
          style: style,
          bounds: SWITZERLAND,
          fitBoundsOptions: { padding: 24 },
          attributionControl: { compact: true },
          dragRotate: false,
          pitchWithRotate: false,
        },
        options || {}
      )
    );
    map.touchZoomRotate.disableRotation();
    return map;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  /* --- The resort map ---------------------------------------------------- */

  async function resortMap(container) {
    const map = await createMap(container);
    const markers = [];
    let selected = null;

    map.on("zoom", function () {
      container.classList.toggle("map-zoomed", map.getZoom() >= 9.5);
    });

    // A pass's pins carry its class (pin--pass-magic-pass), and its name in
    // the label, taken from the pass's chip.
    function passName(slug) {
      const chip = document.querySelector('[data-pass-chip="' + slug + '"]');
      return chip ? chip.textContent.trim() : "";
    }

    function pinElement(pin) {
      const button = el("button", "pin");
      button.type = "button";
      const passes = pin.passes || [];
      const label = [pin.name].concat(passes.map(passName).filter(Boolean));
      if (pin.friends) label.push(pin.friends + " friends");
      button.setAttribute("aria-label", label.join(", "));
      button.dataset.resort = pin.id;
      passes.forEach(function (slug) { button.classList.add("pin--pass-" + slug); });
      if (pin.friends) button.classList.add("pin--friends");
      if (pin.meetup) button.classList.add("pin--meetup");
      if (pin.mine) button.classList.add("pin--mine", "pin--friends");
      const dot = el("span", "pin__dot");
      if (pin.friends) {
        dot.appendChild(el("span", "pin__count", String(pin.friends)));
      }
      button.appendChild(dot);
      button.appendChild(el("span", "pin__name", pin.name));
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        if (selected) selected.classList.remove("pin--selected");
        selected = button;
        button.classList.add("pin--selected");
        const url = container.dataset.sheetUrl.replace("RESORT", pin.id) +
          "?date=" + encodeURIComponent(container.dataset.date);
        htmx.ajax("GET", url, { target: "#sheet-body" });
      });
      return button;
    }

    // Bumped on every load, so a slow response for an earlier pass can't
    // overwrite the pins of the one picked after it.
    let loadCount = 0;

    async function loadPins(fit) {
      const url = container.dataset.pinsUrl + "?date=" + encodeURIComponent(container.dataset.date) +
        "&pass=" + encodeURIComponent(container.dataset.pass || "");
      const load = ++loadCount;
      const response = await fetch(url, { credentials: "same-origin" });
      const data = await response.json();
      if (load !== loadCount) return;
      if (selected && !selected.isConnected) selected = null;
      markers.forEach(function (marker) { marker.remove(); });
      markers.length = 0;
      // Quiet pins first so busy ones draw on top.
      data.pins.sort(function (a, b) { return (a.friends + a.mine) - (b.friends + b.mine); });
      const busy = new maplibregl.LngLatBounds();
      data.pins.forEach(function (pin) {
        const marker = new maplibregl.Marker({
          element: pinElement(pin),
          anchor: "top",
          offset: [0, -8],
        })
          .setLngLat([pin.lng, pin.lat])
          .addTo(map);
        markers.push(marker);
        if (pin.friends || pin.mine || pin.meetup) {
          busy.extend([pin.lng, pin.lat]);
        }
      });
      // Open on the day's action: where friends are, not the whole country.
      // A pass change keeps the view where the person left it.
      if (fit && !busy.isEmpty()) {
        map.fitBounds(busy, {
          padding: { top: 160, bottom: 80, left: 60, right: 60 },
          maxZoom: 9.5,
          duration: 0,
        });
      }
    }

    document.addEventListener("sheet:closed", function () {
      if (selected) selected.classList.remove("pin--selected");
      selected = null;
    });

    /* Picking a pass or a day swaps the pins only. The basemap, the view
       and the page stay as they are, and the URL still says which day and
       pass are showing, so a reload or a shared link opens the same map. */
    const shortDay = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" });
    const dayText = document.querySelector("[data-day-text]");
    const dayButton = document.querySelector("[data-day-label]");
    const todayIso = dayButton ? dayButton.dataset.today : "";

    function localDate(iso) {
      const parts = iso.split("-").map(Number);
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function isoDate(date) {
      const pad = function (n) { return String(n).padStart(2, "0"); };
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
    }

    function shiftDay(iso, n) {
      const date = localDate(iso);
      return isoDate(new Date(date.getFullYear(), date.getMonth(), date.getDate() + n));
    }

    function viewUrl(date, slug) {
      const url = new URL(window.location.href);
      url.searchParams.set("date", date);
      if (slug) {
        url.searchParams.set("pass", slug);
      } else {
        url.searchParams.delete("pass");
      }
      return url.pathname + url.search;
    }

    function showView(date, slug) {
      container.dataset.date = date;
      container.dataset.pass = slug;
      document.querySelectorAll("[data-pass-chip]").forEach(function (chip) {
        chip.href = viewUrl(date, chip.dataset.passChip);
        if (chip.dataset.passChip === slug) {
          chip.setAttribute("aria-current", "true");
        } else {
          chip.removeAttribute("aria-current");
        }
      });
      // The day arrows carry the pass, so moving day keeps the filter.
      document.querySelectorAll("[data-day-link]").forEach(function (link) {
        link.href = viewUrl(shiftDay(date, Number(link.dataset.dayLink)), slug);
      });
      const label = shortDay.format(localDate(date)).replace(",", "");
      if (dayText) dayText.textContent = (date === todayIso ? "Today · " : "") + label;
      if (dayButton) dayButton.dataset.value = date;
      document.title = document.title.replace(/^Map · [^·]+·/, "Map · " + label + " ·");
      if (selected) selected.classList.remove("pin--selected");
      selected = null;
      loadPins(false);
    }

    function go(date, slug) {
      if (date === container.dataset.date && slug === (container.dataset.pass || "")) return;
      history.pushState({ date: date, pass: slug }, "", viewUrl(date, slug));
      showView(date, slug);
    }

    function plainClick(event) {
      return !(event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0);
    }

    document.querySelectorAll("[data-pass-chip]").forEach(function (chip) {
      chip.addEventListener("click", function (event) {
        if (!plainClick(event)) return;
        event.preventDefault();
        go(container.dataset.date, chip.dataset.passChip);
      });
    });

    document.querySelectorAll("[data-day-link]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (!plainClick(event)) return;
        event.preventDefault();
        go(shiftDay(container.dataset.date, Number(link.dataset.dayLink)), container.dataset.pass || "");
      });
    });

    if (dayButton && window.dayCalendar) {
      window.dayCalendar(dayButton, function (date) {
        go(date, container.dataset.pass || "");
      });
    }

    window.addEventListener("popstate", function () {
      const params = new URL(window.location.href).searchParams;
      showView(params.get("date") || todayIso, params.get("pass") || "");
    });

    map.on("load", function () { loadPins(true); });

    const search = document.querySelector("[data-map-search]");
    if (search) {
      resortSearch(search, function (resort) {
        map.flyTo({ center: [resort.lng, resort.lat], zoom: 12.5, essential: true });
        // Mark its pin, if the current pass shows one.
        const pin = container.querySelector('[data-resort="' + resort.id + '"]');
        if (selected) selected.classList.remove("pin--selected");
        selected = pin;
        if (pin) pin.classList.add("pin--selected");
      });
    }
  }

  /* --- Resort search ----------------------------------------------------- */

  // Lowercase with accents removed, so "champery" finds Champéry.
  function fold(text) {
    return text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  // Same order as apps/resorts/search.py: code, name start, word start, anywhere.
  function rank(resort, query) {
    const name = fold(resort.name);
    if (resort.code && fold(resort.code) === query) return 0;
    if (name.startsWith(query)) return 1;
    if (name.replace(/-/g, " ").split(/\s+/).some(function (w) { return w.startsWith(query); })) return 2;
    if (name.includes(query)) return 3;
    return null;
  }

  function resortSearch(root, onPick) {
    const input = root.querySelector("input");
    const list = root.querySelector("[role=listbox]");
    const index = JSON.parse(document.getElementById("resort-index").textContent);
    const LIMIT = 8;
    let matches = [];
    let active = -1;

    function close() {
      list.hidden = true;
      list.replaceChildren();
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      matches = [];
      active = -1;
    }

    function highlight(i) {
      active = i;
      Array.from(list.children).forEach(function (option, n) {
        option.setAttribute("aria-selected", n === i ? "true" : "false");
      });
      if (i >= 0) {
        input.setAttribute("aria-activedescendant", list.children[i].id);
        list.children[i].scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }

    function pick(resort) {
      input.value = resort.name;
      close();
      input.blur();
      onPick(resort);
    }

    function render() {
      const query = fold(input.value.trim());
      if (!query) return close();
      matches = index
        .map(function (resort) { return [rank(resort, query), resort]; })
        .filter(function (pair) { return pair[0] !== null; })
        .sort(function (a, b) { return a[0] - b[0] || a[1].name.localeCompare(b[1].name); })
        .slice(0, LIMIT)
        .map(function (pair) { return pair[1]; });
      list.replaceChildren();
      if (!matches.length) {
        const empty = el("li", "map-search__empty", "No resort matches");
        empty.setAttribute("role", "presentation");
        list.appendChild(empty);
      }
      matches.forEach(function (resort, n) {
        const option = el("li", "map-search__option");
        option.id = "map-search-option-" + n;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.appendChild(el("span", "map-search__name", resort.name));
        if (resort.canton) option.appendChild(el("span", "map-search__canton", resort.canton));
        // pointerdown, so the pick lands before the input's blur closes the list.
        option.addEventListener("pointerdown", function (event) {
          event.preventDefault();
          pick(resort);
        });
        list.appendChild(option);
      });
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      highlight(matches.length ? 0 : -1);
    }

    input.addEventListener("input", render);
    input.addEventListener("focus", function () { if (input.value.trim()) render(); });
    input.addEventListener("blur", close);
    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown" && matches.length) {
        event.preventDefault();
        highlight((active + 1) % matches.length);
      } else if (event.key === "ArrowUp" && matches.length) {
        event.preventDefault();
        highlight((active - 1 + matches.length) % matches.length);
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (active >= 0) pick(matches[active]);
      } else if (event.key === "Escape") {
        if (!list.hidden) {
          event.preventDefault();
          close();
        } else {
          input.value = "";
        }
      }
    });
  }

  /* --- Meeting-pin picker ------------------------------------------------ */

  async function pinPicker(container) {
    const lat = parseFloat(container.dataset.lat);
    const lng = parseFloat(container.dataset.lng);
    const form = container.closest("form");
    const latInput = form.querySelector("[name=meeting_latitude]");
    const lngInput = form.querySelector("[name=meeting_longitude]");
    const clear = form.querySelector("[data-clear-pin]");
    const options = isNaN(lat) ? {} : { center: [lng, lat], zoom: 13, bounds: undefined };
    const map = await createMap(container, options);
    let marker = null;

    function place(lngLat) {
      if (!marker) {
        const node = el("div");
        node.innerHTML = container.dataset.pinSvg;
        marker = new maplibregl.Marker({ element: node.firstElementChild, anchor: "bottom" });
        marker.setLngLat(lngLat).addTo(map);
      } else {
        marker.setLngLat(lngLat);
      }
      latInput.value = lngLat.lat.toFixed(6);
      lngInput.value = lngLat.lng.toFixed(6);
      if (clear) clear.hidden = false;
    }

    if (latInput.value && lngInput.value) {
      place({ lat: parseFloat(latInput.value), lng: parseFloat(lngInput.value) });
    }
    map.on("click", function (event) { place(event.lngLat); });
    if (clear) {
      clear.addEventListener("click", function () {
        if (marker) marker.remove();
        marker = null;
        latInput.value = "";
        lngInput.value = "";
        clear.hidden = true;
      });
    }
    // Recentre on the resort when a different one is picked.
    form.addEventListener("change", function (event) {
      const option = event.target.closest("[data-lat]");
      if (event.target.name === "resort" && option && option.dataset.lat) {
        map.flyTo({ center: [parseFloat(option.dataset.lng), parseFloat(option.dataset.lat)], zoom: 13 });
      }
    });
  }

  /* --- A meet-up's small map --------------------------------------------- */

  async function meetupMap(container) {
    const lat = parseFloat(container.dataset.lat);
    const lng = parseFloat(container.dataset.lng);
    const map = await createMap(container, {
      center: [lng, lat],
      zoom: 13,
      bounds: undefined,
      interactive: false,
    });
    const node = el("div");
    node.innerHTML = container.dataset.pinSvg;
    new maplibregl.Marker({ element: node.firstElementChild, anchor: "bottom" })
      .setLngLat([lng, lat])
      .addTo(map);
  }

  document.querySelectorAll("[data-resort-map]").forEach(resortMap);
  document.querySelectorAll("[data-pin-picker]").forEach(pinPicker);
  document.querySelectorAll("[data-meetup-map]").forEach(meetupMap);
})();
