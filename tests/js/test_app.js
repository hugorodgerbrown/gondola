// Tests for static/js/app.js: Gondola's first, site-wide service worker is retired.
import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('retireRootWorker', () => {
  it("unregisters the site-wide worker, keeps the app's, and drops the old caches", async () => {
    const root = { scope: location.origin + '/', unregister: vi.fn(async () => true) };
    const app = { scope: location.origin + '/app/', unregister: vi.fn(async () => true) };
    vi.stubGlobal('navigator', {
      ...navigator,
      serviceWorker: { getRegistrations: vi.fn(async () => [root, app]) },
    });
    const deleted = vi.fn(async () => true);
    vi.stubGlobal('caches', { delete: deleted });

    await import('../../static/js/app.js?' + Math.random());
    await window.retireRootWorker();

    expect(root.unregister).toHaveBeenCalled();
    expect(app.unregister).not.toHaveBeenCalled();
    expect(deleted.mock.calls.map(([name]) => name)).toEqual(
      expect.arrayContaining(['static-v1', 'pages-v1'])
    );
  });

  it('does nothing where there is no service worker', async () => {
    vi.stubGlobal('navigator', { userAgent: 'test' });
    vi.stubGlobal('caches', undefined);
    await import('../../static/js/app.js?' + Math.random());
    await expect(window.retireRootWorker()).resolves.toBeDefined();
  });
});

describe('calendar arrow keys', () => {
  // Each import adds its own listener to the one document: take them off
  // again, so one test's page can't step another's.
  let listeners = [];

  async function load(html) {
    const add = document.addEventListener.bind(document);
    vi.spyOn(document, 'addEventListener').mockImplementation((type, listener, options) => {
      listeners.push([type, listener, options]);
      add(type, listener, options);
    });
    document.body.innerHTML = html;
    const page = { href: '/app/calendar/', origin: 'http://localhost' };
    vi.stubGlobal('location', page);
    vi.stubGlobal('navigator', { userAgent: 'test' });
    vi.stubGlobal('caches', undefined);
    await import('../../static/js/app.js?' + Math.random());
    return page;
  }

  const MONTH =
    '<div class="month" data-swipe-previous="?from=2026-11-01" data-swipe-next="?from=2027-01-01">' +
    '<a href="#" id="day">13</a></div>';

  function press(key, options = {}, target = document.body) {
    const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...options });
    target.dispatchEvent(event);
    return event;
  }

  afterEach(() => {
    listeners.forEach(([type, listener, options]) => document.removeEventListener(type, listener, options));
    listeners = [];
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  it('steps back a month on Left and on a month on Right', async () => {
    const page = await load(MONTH);
    expect(press('ArrowLeft').defaultPrevented).toBe(true);
    expect(page.href).toBe('?from=2026-11-01');
    press('ArrowRight', {}, document.getElementById('day'));
    expect(page.href).toBe('?from=2027-01-01');
  });

  it('stays put at the end of the season', async () => {
    const page = await load('<div class="month" data-swipe-previous="?from=2026-11-01"></div>');
    expect(press('ArrowRight').defaultPrevented).toBe(false);
    expect(page.href).toBe('/app/calendar/');
  });

  it('ignores other keys and arrows with a modifier held', async () => {
    const page = await load(MONTH);
    press('ArrowUp');
    for (const modifier of ['altKey', 'ctrlKey', 'metaKey', 'shiftKey']) {
      press('ArrowLeft', { [modifier]: true });
    }
    expect(page.href).toBe('/app/calendar/');
  });

  it('leaves the arrows to a field being typed in', async () => {
    const page = await load(
      MONTH + '<input id="field"><textarea id="note"></textarea><select id="pick"></select>' +
      '<div contenteditable="true" id="rich"></div>'
    );
    for (const id of ['field', 'note', 'pick', 'rich']) {
      press('ArrowLeft', {}, document.getElementById(id));
    }
    expect(page.href).toBe('/app/calendar/');
  });

  it('leaves the arrows to an open sheet or popup calendar', async () => {
    const page = await load(MONTH + '<dialog id="sheet" open></dialog>');
    press('ArrowLeft');
    document.getElementById('sheet').removeAttribute('open');
    document.body.insertAdjacentHTML('beforeend', '<div role="dialog"></div>');
    press('ArrowLeft');
    expect(page.href).toBe('/app/calendar/');
  });

  it('does not step when something else handled the key', async () => {
    const page = await load(MONTH);
    document.getElementById('day').addEventListener('keydown', (event) => event.preventDefault());
    press('ArrowLeft', {}, document.getElementById('day'));
    expect(page.href).toBe('/app/calendar/');
  });

  it('listens only on a page with a month calendar', async () => {
    const page = await load('<p>Board</p>');
    press('ArrowLeft');
    expect(page.href).toBe('/app/calendar/');
  });
});
