// Tests for static/js/plans.js: plan-day forms go through the outbox and draw as waiting.
import { afterEach, describe, expect, it, vi } from 'vitest';

const URL = '/app/days/plans/';

function sheetForm(attrs, inner = '') {
  const form = document.createElement('form');
  form.method = 'post';
  form.action = '/app/days/2026-12-14/';
  Object.entries({ planWrite: 'set', days: '2026-12-14', plansUrl: URL, ...attrs }).forEach(
    ([key, value]) => {
      form.dataset[key] = value;
    }
  );
  form.innerHTML = inner + '<button type="submit">Save</button>';
  document.body.appendChild(form);
  return form;
}

const RADIOS =
  '<input type="radio" name="resort" value="r-verbier" data-code="VERB">' +
  '<input type="radio" name="resort" value="r-zermatt" data-code="ZERM">';

function cell(date, html = '<span class="mday__row"></span><span class="mday__row"></span>') {
  const el = document.createElement('a');
  el.className = 'mday mday--friends';
  el.dataset.date = date;
  el.innerHTML = html;
  document.body.appendChild(el);
  return el;
}

async function load(outbox) {
  vi.resetModules();
  if (outbox) self.Outbox = outbox;
  document.body.dataset.plansUrl = URL;
  await import('../../static/js/plans.js?' + Math.random());
  return self.Plans;
}

afterEach(() => {
  delete self.Outbox;
  delete self.Plans;
  document.body.innerHTML = '';
  vi.unstubAllGlobals();
});

describe('fromForm', () => {
  it('reads the checked resort and its code', async () => {
    const Plans = await load();
    const form = sheetForm({ days: '2026-12-14,2026-12-15' }, RADIOS);
    form.querySelector('[value="r-zermatt"]').checked = true;
    expect(Plans.fromForm(form)).toEqual({
      url: URL,
      days: ['2026-12-14', '2026-12-15'],
      resort: 'r-zermatt',
      code: 'ZERM',
    });
  });

  it('takes a fixed resort from the form (the map\'s "I\'ll be here")', async () => {
    const Plans = await load();
    const form = sheetForm({ resort: 'r-verbier', code: 'VERB' });
    expect(Plans.fromForm(form).resort).toBe('r-verbier');
  });

  it('clears with no resort', async () => {
    const Plans = await load();
    expect(Plans.fromForm(sheetForm({ planWrite: 'clear' }))).toMatchObject({ resort: null });
  });

  it('leaves the form alone when no resort is picked, or nothing is marked', async () => {
    const Plans = await load();
    expect(Plans.fromForm(sheetForm({}, RADIOS))).toBeNull();
    expect(Plans.fromForm(sheetForm({ days: '' }))).toBeNull();
    expect(Plans.fromForm(sheetForm({ planWrite: 'other' }))).toBeNull();
  });
});

describe('pendingDays and markCalendar', () => {
  it("keeps each day's latest answer, and marks failures", async () => {
    const Plans = await load();
    const rows = [
      { id: 2, url: URL, status: 'failed', meta: { days: ['2026-12-15'], resort: null } },
      { id: 1, url: URL, status: 'pending', meta: { days: ['2026-12-14', '2026-12-15'], resort: 'r', code: 'VERB' } },
      { id: 3, url: '/other/', status: 'pending', meta: { days: ['2026-12-16'], resort: 'x' } },
    ];
    expect(Plans.pendingDays(rows, URL)).toEqual({
      '2026-12-14': { resort: 'r', code: 'VERB', failed: false },
      '2026-12-15': { resort: null, code: '', failed: true },
    });
  });

  it('draws a saved day blue and striped with its code, a cleared one plain', async () => {
    const Plans = await load();
    const saved = cell('2026-12-14');
    const cleared = cell(
      '2026-12-15',
      '<span class="mday__row"></span><span class="mday__row"><span class="mday__resort">ZERM</span></span>'
    );
    const untouched = cell('2026-12-16');
    Plans.markCalendar(document, {
      '2026-12-14': { resort: 'r', code: 'VERB', failed: false },
      '2026-12-15': { resort: null, code: '', failed: false },
    });
    expect(saved.className).toBe('mday mday--pending mday--in');
    expect(saved.querySelector('.mday__resort').textContent).toBe('VERB');
    expect(cleared.classList.contains('mday--in')).toBe(false);
    expect(cleared.classList.contains('mday--pending')).toBe(true);
    expect(cleared.querySelector('.mday__resort').textContent).toBe('');
    expect(untouched.className).toBe('mday mday--friends');
  });
});

describe('submitting a sheet', () => {
  function fakeOutbox(rows = []) {
    return {
      rows,
      enqueue: vi.fn(async (row) => {
        rows.push({ id: rows.length + 1, url: row.url, status: 'pending', meta: row.meta });
      }),
      list: vi.fn(async () => ({ pending: rows.filter((r) => r.status === 'pending'), failed: [] })),
    };
  }

  it('queues the write instead of posting, and closes the sheet', async () => {
    const outbox = fakeOutbox();
    await load(outbox);
    const dialog = document.createElement('dialog');
    dialog.id = 'sheet';
    dialog.close = vi.fn();
    Object.defineProperty(dialog, 'open', { value: true });
    document.body.appendChild(dialog);
    const form = sheetForm({}, RADIOS);
    form.querySelector('[value="r-verbier"]').checked = true;
    const posted = vi.fn((event) => event.preventDefault());
    form.addEventListener('submit', posted);

    form.requestSubmit();
    await vi.waitFor(() => expect(dialog.close).toHaveBeenCalled());

    expect(posted).not.toHaveBeenCalled();
    const sent = outbox.enqueue.mock.calls[0][0];
    expect(sent.url).toBe(URL);
    expect(JSON.parse(sent.body)).toMatchObject({ days: ['2026-12-14'], resort: 'r-verbier' });
    expect(JSON.parse(sent.body).written_at).toMatch(/Z$/);
    expect(sent.meta).toEqual({ days: ['2026-12-14'], resort: 'r-verbier', code: 'VERB' });
  });

  it('lets a form with no resort picked post, so the server can say so', async () => {
    const outbox = fakeOutbox();
    await load(outbox);
    const form = sheetForm({}, RADIOS);
    const posted = vi.fn((event) => event.preventDefault());
    form.addEventListener('submit', posted);
    form.requestSubmit();
    expect(posted).toHaveBeenCalled();
    expect(outbox.enqueue).not.toHaveBeenCalled();
  });

  it('reloads once a queued write has gone', async () => {
    const reload = vi.fn();
    vi.stubGlobal('location', { reload, assign: vi.fn() });
    const rows = [{ id: 1, url: URL, status: 'pending', meta: { days: ['2026-12-14'], resort: 'r' } }];
    const outbox = fakeOutbox(rows);
    await load(outbox);
    await vi.waitFor(() => expect(outbox.list).toHaveBeenCalled());
    rows.length = 0;
    document.dispatchEvent(new CustomEvent('outbox:changed', { detail: {} }));
    await vi.waitFor(() => expect(reload).toHaveBeenCalled());
  });
});
