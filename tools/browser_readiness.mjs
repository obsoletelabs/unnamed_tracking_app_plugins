/** Readiness helpers for browser checks that drive a freshly started Vite dev server. */

/** Resolve once `url` answers OK; throw (instead of silently continuing) if it never does. */
export async function waitForServer(url, { timeoutMs = 90000, intervalMs = 250, fetchImpl = fetch } = {}) {
  const deadline = Date.now() + timeoutMs;
  let last = "no response";
  while (Date.now() < deadline) {
    try {
      const response = await fetchImpl(url);
      if (response.ok) return;
      last = `HTTP ${response.status}`;
    } catch (error) {
      last = error.message;
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  throw new Error(`${url} was not ready after ${timeoutMs}ms (${last})`);
}

/**
 * Navigate and wait for `ready`, reloading once if it does not appear.
 *
 * A cold Vite server optimises dependencies on first use and may reload the page while it
 * does so, which can discard the first render; one reload exercises the warmed server
 * without hiding a page that genuinely never renders (the second wait still fails).
 */
export async function gotoWhenReady(page, url, ready, { firstWaitMs = 30000, finalWaitMs = 60000 } = {}) {
  await page.goto(url);
  try {
    await ready().waitFor({ timeout: firstWaitMs });
  } catch (error) {
    if (error?.name !== "TimeoutError") throw error;
    await page.reload();
    await ready().waitFor({ timeout: finalWaitMs });
  }
}
