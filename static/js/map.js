/*
 * static/js/map.js — Every map in the app: the resort map, the meeting-pin
 * picker on the meet-up form, and the small map on a meet-up page.
 *
 * The basemap is MAP_STYLE_URL (OpenFreeMap by default). If it can't be
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

    function pinElement(pin) {
      const button = el("button", "pin");
      button.type = "button";
      button.setAttribute(
        "aria-label",
        pin.name + (pin.friends ? ", " + pin.friends + " friends" : "")
      );
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

    async function loadPins() {
      const url = container.dataset.pinsUrl + "?date=" + encodeURIComponent(container.dataset.date) +
        "&pass=" + encodeURIComponent(container.dataset.pass || "");
      const response = await fetch(url, { credentials: "same-origin" });
      const data = await response.json();
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
      if (!busy.isEmpty()) {
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

    map.on("load", loadPins);
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
