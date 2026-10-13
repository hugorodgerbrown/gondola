"""What the design page leaves out, and why.

tests/test_design.py fails when a component in app.css isn't on the design
page. A component that can't sit on the page (the page's own frame, a
screen that covers everything) is named here with the reason instead.
"""

# Component (block) class -> why it isn't on the design page.
NOT_ON_PAGE: dict[str, str] = {
    "topbar": "the frame of every page, the design page included",
    "tabbar": "the frame of every page, the design page included",
    "page": "the frame of every page, the design page included",
    "sheet-page": "a sheet opened as a page of its own, without JavaScript",
    "site-footer": "the frame of every public page",
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
ADDED_BY_FRAMEWORKS: dict[str, str] = {}
