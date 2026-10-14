"""The exceptions to the rules in DESIGN.md, each with its reason.

tests/test_design.py fails when a component in app.css isn't on the design
page. A component that can't sit on the page (the page's own frame, a
screen that covers everything) is named here with the reason instead. The
same goes for a script under /app/ that isn't precached for offline use.
"""

# Component (block) class -> why it isn't on the design page.
NOT_ON_PAGE: dict[str, str] = {
    "topbar": "the frame of every page, the design page included",
    "tabbar": "the frame of every page, the design page included",
    "page": "the frame of every page, the design page included",
    "sheet-page": "a sheet opened as a page of its own, without JavaScript",
    "offline-banner": "the frame of every page; shown while offline",
    "outbox-status": "the frame of every page; shown while writes wait to send",
    "launch-shell": "covers the whole screen while the app launches",
    "app-launching": "the state the launch screen is in, set on <html>",
    "htmx-indicator": "htmx's own request state",
    "htmx-request": "htmx's own request state",
    "map-page": "the map screen's frame: the map fills the screen",
    "map-canvas": "the map screen's frame: MapLibre draws into it",
    "map-overlay": "the map screen's frame: holds the controls over the map",
    "map-zoomed": "a state map.js puts on the map when zoomed in",
    "has-select-bar": "a state day_select.js puts on <body>",
    "tour-layer": "covers the whole screen during the tour",
    "tour-shade": "covers the whole screen during the tour",
    "tour-ring": "drawn round a part of the real screen during the tour",
}

# Classes a framework puts on elements (no template here names them), so the
# dead-CSS check counts them as used.
ADDED_BY_FRAMEWORKS: dict[str, str] = {
    "errorlist": "Django renders it round a form's errors",
}

# Scripts and stylesheets a page under /app/ loads that aren't precached,
# because they only work with the network anyway (DESIGN.md, section 11).
NEEDS_NETWORK: dict[str, str] = {
    "js/analytics.js": "analytics only send with the network; pages work without them",
    "js/webauthn_json.js": "passkeys need the server to sign in or register",
    "js/passkeys.js": "passkeys need the server to sign in or register",
    "js/design.js": "the design page is a staff reference, not the app",
    "js/tour.js": "the tour walks a demo group the server keeps",
    "js/map.js": "the map draws resort tiles fetched from the network",
    "js/calendar.js": "the map's day picker, which needs the map",
    "vendor/maplibre-gl-4.7.1.js": "the map needs its tiles from the network; too big to precache",
    "vendor/maplibre-gl-4.7.1.css": "the map needs its tiles from the network",
}
