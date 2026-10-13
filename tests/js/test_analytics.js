// Tests for static/js/analytics.js: the events the server queued are sent once.
import { afterEach, describe, expect, it, vi } from 'vitest';

function queue(text) {
  const script = document.createElement('script');
  script.id = 'analytics-events';
  script.type = 'application/json';
  script.textContent = text;
  document.body.appendChild(script);
}

afterEach(() => {
  vi.resetModules();
  delete window.tally;
  document.body.innerHTML = '';
});

describe('analytics', () => {
  it('queues the events before fivebar has loaded', async () => {
    queue('[["Sign up", {}], ["Day said", {"days": 3}]]');
    await import('../../static/js/analytics.js?queue');
    expect(window.tally).toEqual([
      ['Sign up', {}],
      ['Day said', { days: 3 }],
    ]);
  });

  it('calls fivebar directly once it has loaded', async () => {
    window.tally = vi.fn();
    queue('[["Sign up", null]]');
    await import('../../static/js/analytics.js?loaded');
    expect(window.tally).toHaveBeenCalledWith('Sign up', {});
  });

  it('sends nothing when the page queued nothing', async () => {
    await import('../../static/js/analytics.js?none');
    expect(window.tally).toBeUndefined();
  });

  it('loses a broken queue, never the page', async () => {
    queue('not json');
    await import('../../static/js/analytics.js?broken');
    expect(window.tally).toBeUndefined();
    expect(window.Analytics.send).toBeTypeOf('function');
  });
});
