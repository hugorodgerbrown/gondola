/*
 * static/js/analytics.js — send fivebar the events the server queued.
 *
 * Loaded with fivebar's tag, only while FIVEBAR_DOMAIN is set
 * (templates/includes/analytics.html). fivebar counts pages by itself;
 * this file adds events, the things people do that a page view can't show.
 * Every event is a goal on fivebar's dashboard.
 *
 * The server queues an event in the session (apps/core/analytics.py:
 * record) and the next full page writes the queue into #analytics-events,
 * as [name, data] pairs. A click that is itself the event carries
 * data-tally in its template, which fivebar's script sends by itself.
 *
 * fivebar's script is async and may load before or after this one: once it
 * has, `tally` is its function; until then it is a queue it sends on load.
 */
(function () {
  "use strict";

  function send(name, data) {
    if (typeof window.tally === "function") window.tally(name, data || {});
    else (window.tally = window.tally || []).push([name, data || {}]);
  }

  const queued = document.getElementById("analytics-events");
  if (queued) {
    try {
      JSON.parse(queued.textContent).forEach(function (event) {
        send(event[0], event[1]);
      });
    } catch (error) {
      // A broken queue loses its events, never the page.
    }
  }

  window.Analytics = Object.freeze({ send: send });
})();
