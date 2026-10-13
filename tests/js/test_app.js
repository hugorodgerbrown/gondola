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
