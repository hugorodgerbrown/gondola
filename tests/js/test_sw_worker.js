<<<<<<< before updating
// Tests for static/js/sw_worker.js: re-caching a page never outlives a sign-out,
// and a sheet fragment never stands in for its page.
=======
// Tests for static/js/sw_worker.js: a cached page never outlives a sign-out.
>>>>>>> after updating
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/idb.js';
import '../../static/js/outbox_core.js';
import '../../static/js/outbox.js';
import '../../static/js/sw_core.js';

const { AppDB } = self;
const stored = new Map();
let onMessage;
let onFetch;
<<<<<<< before updating
const keyOf = (key) => (key instanceof Request ? key.url : String(key));
=======
>>>>>>> after updating

beforeAll(async () => {
  self.SW_CONFIG = {
    prefix: 'app',
    version: 'v1',
    staticUrl: '/static/',
    scope: '/app/',
    workerUrl: '/app/sw.js',
    neverCache: [],
    precache: [],
    offlineUrl: '/app/offline/',
  };
  const add = vi.spyOn(self, 'addEventListener');
  await import('../../static/js/sw_worker.js');
  onMessage = add.mock.calls.find(([type]) => type === 'message')[1];
  onFetch = add.mock.calls.find(([type]) => type === 'fetch')[1];
  add.mockRestore();
});

beforeEach(async () => {
  stored.clear();
  vi.stubGlobal('caches', {
    open: async () => ({
<<<<<<< before updating
      put: async (url, response) => stored.set(keyOf(url), response),
      delete: async (url) => stored.delete(keyOf(url)),
      match: async (url) => stored.get(keyOf(url)),
=======
      put: async (url, response) => stored.set(String(url.url ?? url), response),
      delete: async (url) => stored.delete(String(url.url ?? url)),
      match: async (url) => stored.get(String(url.url ?? url)),
>>>>>>> after updating
    }),
    delete: async () => stored.clear(),
  });
  await AppDB.setMeta('principal', '7');
});

/** Post 'cache-page' for /app/ and wait for the worker to finish with it. */
async function cachePage(fetchImpl) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  let work;
  onMessage({ data: { type: 'cache-page', url: '/app/' }, waitUntil: (promise) => (work = promise) });
  await work;
  return [...stored.keys()].some((url) => url.endsWith('/app/'));
}

const page = () => ({ ok: true, redirected: false, type: 'basic', headers: new Headers() });

describe('cache-page', () => {
  it('stores the page for the signed-in user', async () => {
    expect(await cachePage(async () => page())).toBe(true);
  });

  it('takes the copy out again when a sign-out started during the fetch', async () => {
    const cached = await cachePage(async () => {
      await AppDB.setMeta('principal', '');
      return page();
    });
    expect(cached).toBe(false);
  });

  it('takes the copy out when another user signed in during the fetch', async () => {
    const cached = await cachePage(async () => {
      await AppDB.setMeta('principal', '8');
      return page();
    });
    expect(cached).toBe(false);
  });

  it('fetches nothing once signed out', async () => {
    await AppDB.setMeta('principal', '');
    expect(await cachePage(async () => page())).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
  });
});

<<<<<<< before updating

describe('fetch', () => {
  const URL = self.location.origin + '/app/days/2026-12-14/';

  async function get(headers, fetchImpl) {
    vi.stubGlobal('fetch', vi.fn(fetchImpl));
    let answer;
    const work = [];
    const request = new Request(URL, { headers });
    onFetch({ request, respondWith: (p) => (answer = p), waitUntil: (p) => work.push(p) });
    const response = await answer;
    await Promise.all(work);
    return response;
  }

  const body = (text) => async () => ({
    ok: true,
    redirected: false,
    type: 'basic',
    headers: new Headers(),
    clone: () => text,
  });

  it('keeps an htmx fragment apart from the page at the same address', async () => {
    await get({}, body('page'));
    await get({ 'HX-Request': 'true' }, body('fragment'));
    expect(stored.get(URL)).toBe('page');
    expect(stored.get(URL + '?__htmx=1')).toBe('fragment');
  });

  it('answers each kind offline from its own copy', async () => {
    stored.set(URL, 'page');
    stored.set(URL + '?__htmx=1', 'fragment');
    const offline = async () => {
      throw new TypeError('offline');
    };
    expect(await get({}, offline)).toBe('page');
    expect(await get({ 'HX-Request': 'true' }, offline)).toBe('fragment');
=======
/** Navigate to /app/ through the worker's fetch handler and wait for it to finish. */
async function visit(response) {
  vi.stubGlobal('fetch', vi.fn(async () => response));
  const work = [];
  let reply;
  const request = { url: `${self.location.origin}/app/`, method: 'GET', mode: 'navigate' };
  onFetch({ request, respondWith: (promise) => (reply = promise), waitUntil: (promise) => work.push(promise) });
  await reply;
  await Promise.all(work);
}

describe('page fetch', () => {
  const cachedUrl = () => `${self.location.origin}/app/`;
  const otherUrl = () => `${self.location.origin}/app/other/`;

  it.each([
    ['sent on to sign-in', { redirected: true }],
    ['refused', { ok: false, status: 403 }],
  ])('forgets every cached page and the principal when a page is %s', async (_, overrides) => {
    stored.set(cachedUrl(), page());
    stored.set(otherUrl(), page());
    await visit({ ...page(), ...overrides });
    expect(stored.size).toBe(0);
    expect(await AppDB.getMeta('principal')).toBe('');
  });

  it('still forgets the pages when a slow sign-out arrives after the cached copy', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout'] });
    try {
      stored.set(cachedUrl(), page());
      let answer;
      vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => (answer = resolve))));
      const events = [];
      let reply;
      const request = { url: cachedUrl(), method: 'GET', mode: 'navigate' };
      onFetch({
        request,
        respondWith: (promise) => (reply = promise.then((r) => (events.push('replied'), r))),
        waitUntil: (promise) => (events.push('waitUntil'), (reply.cleanup = promise)),
      });
      await vi.advanceTimersByTimeAsync(4000);
      expect(await reply).toBe(stored.get(cachedUrl()));
      answer({ ...page(), redirected: true });
      await reply.cleanup;
      expect(events).toEqual(['waitUntil', 'replied']);
      expect(stored.size).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps the cached copy through a server error', async () => {
    stored.set(cachedUrl(), page());
    await visit({ ...page(), ok: false, status: 500 });
    expect(stored.has(cachedUrl())).toBe(true);
>>>>>>> after updating
  });
});
