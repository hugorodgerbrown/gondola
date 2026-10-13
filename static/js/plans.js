/*
 * static/js/plans.js — save and clear plan days through the outbox.
 *
 * Without this file the sheets' forms post normally. With it, a form
 * marked data-plan-write ("set" or "clear") is stored on the device first
 * (Outbox.enqueue), the sheet closes, and the calendar draws those days at
 * once as waiting: striped, with the resort's code. The outbox sends them
 * when there is signal; once a write has gone (or been discarded), the
 * page reloads to show what the server now holds.
 *
 * The form carries what the write needs: data-days (ISO dates, comma
 * separated), data-plans-url (the JSON endpoint), data-done (where to go
 * when the sheet is a page of its own), and for "I'll be here" a fixed
 * data-resort and data-code. Otherwise the resort is the checked radio,
 * and its data-code. A "set" with no resort picked posts as before, so
 * the server says "Pick a resort."
 */
(function () {
  'use strict';

  /** The write a form describes, or null to let it post as a plain form. */
  function fromForm(form) {
    const kind = form.dataset.planWrite;
    const days = (form.dataset.days || '').split(',').filter(Boolean);
    if (!days.length || !form.dataset.plansUrl) return null;
    if (kind === 'clear') return { url: form.dataset.plansUrl, days: days, resort: null, code: '' };
    if (kind !== 'set') return null;
    const checked = form.querySelector('input[name="resort"]:checked');
    const resort = form.dataset.resort || (checked && checked.value);
    if (!resort) return null;
    const code = form.dataset.code || (checked && checked.dataset.code) || '';
    return { url: form.dataset.plansUrl, days: days, resort: resort, code: code };
  }

  /** Each day's latest queued answer: {resort, code, failed}, oldest rows first. */
  function pendingDays(rows, url) {
    const days = {};
    rows
      .filter((row) => row.url === url && row.meta && Array.isArray(row.meta.days))
      .sort((a, b) => a.id - b.id)
      .forEach((row) => {
        row.meta.days.forEach((day) => {
          days[day] = {
            resort: row.meta.resort || null,
            code: row.meta.code || '',
            failed: row.status === 'failed',
          };
        });
      });
    return days;
  }

  /** Draw ``days`` (from pendingDays) on the calendar's cells. */
  function markCalendar(root, days) {
    root.querySelectorAll('.mday[data-date]').forEach((cell) => {
      const plan = days[cell.dataset.date];
      if (!plan) return;
      cell.classList.add('mday--pending');
      cell.classList.toggle('mday--failed', plan.failed);
      cell.classList.toggle('mday--in', Boolean(plan.resort));
      cell.classList.remove('mday--friends');
      const rows = cell.querySelectorAll('.mday__row');
      const row = rows[rows.length - 1];
      if (!row) return;
      let code = row.querySelector('.mday__resort');
      if (!code) {
        code = document.createElement('span');
        code.className = 'mday__resort';
        row.appendChild(code);
      }
      code.textContent = plan.resort ? plan.code : '';
    });
  }

  self.Plans = { fromForm: fromForm, pendingDays: pendingDays, markCalendar: markCalendar };

  const outbox = self.Outbox;
  if (!outbox || typeof document === 'undefined') return;
  // On <body>, so every page can draw the waiting days, sheet open or not.
  const url = document.body.dataset.plansUrl || '';
  let queued = -1; // our rows at the last look; -1 before the first

  async function draw() {
    const { pending, failed } = await outbox.list();
    const rows = pending.concat(failed);
    const ours = rows.filter((row) => row.url === url).length;
    if (queued > 0 && ours < queued) {
      // Sent or discarded: show what the server holds now.
      location.reload();
      return;
    }
    queued = ours;
    markCalendar(document, pendingDays(rows, url));
  }

  // Capture, so the plain or htmx post never starts.
  document.addEventListener(
    'submit',
    async (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || !form.dataset.planWrite) return;
      const write = fromForm(form);
      if (!write) return;
      event.preventDefault();
      event.stopPropagation();
      await outbox.enqueue({
        url: write.url,
        body: JSON.stringify({
          days: write.days,
          resort: write.resort,
          written_at: new Date().toISOString(),
        }),
        meta: { days: write.days, resort: write.resort, code: write.code },
      });
      const sheet = document.getElementById('sheet');
      if (sheet && sheet.open) {
        sheet.close();
      } else if (form.dataset.done) {
        location.assign(form.dataset.done);
      }
    },
    true
  );

  document.addEventListener('outbox:changed', draw);
  draw();
})();
