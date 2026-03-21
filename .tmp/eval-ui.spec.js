const { test, expect } = require('playwright/test');
const fs = require('fs');

const baseUrl = 'http://127.0.0.1:8000';
const resultsPath = '/Users/willem/Development/news_app/.tmp/eval-ui-results.json';

async function login(page) {
  const adminPassword = process.env.ADMIN_PASSWORD;
  if (!adminPassword) {
    throw new Error('Missing ADMIN_PASSWORD');
  }

  await page.goto(`${baseUrl}/auth/admin/login?next=/admin/evals/summaries`, {
    waitUntil: 'networkidle',
  });

  if (await page.locator('#password').count()) {
    await page.fill('#password', adminPassword);
    await page.click('#submit-btn');
    await page.waitForURL(/\/admin\/evals\/summaries/, { timeout: 15000 });
  }

  await expect(page.locator('#run-eval-btn')).toBeVisible();
}

async function setCheckboxes(page, selector, wantedValues) {
  await page.$$eval(
    selector,
    (nodes, wanted) => {
      for (const node of nodes) {
        node.checked = wanted.includes(node.value);
        node.dispatchEvent(new Event('change', { bubbles: true }));
        node.dispatchEvent(new Event('input', { bubbles: true }));
      }
    },
    wantedValues
  );
}

async function runEval(page, name, config) {
  await login(page);
  await setCheckboxes(page, '.content-type', config.contentTypes);
  await setCheckboxes(page, '.model-option', config.models);
  await page.fill('#recent-pool-size', String(config.recentPoolSize));
  await page.fill('#sample-size', String(config.sampleSize));
  await page.fill('#seed', String(config.seed));

  await page.click('#run-eval-btn');

  const outcome = await page.waitForFunction(
    () => {
      const status = document.querySelector('#run-status')?.textContent?.trim() || '';
      const errorEl = document.querySelector('#run-error');
      const hasVisibleError =
        errorEl &&
        !errorEl.classList.contains('hidden') &&
        errorEl.textContent.trim().length > 0;

      if (status === 'Done') {
        return { status, error: null };
      }
      if (status === 'Failed' || hasVisibleError) {
        return {
          status: status || 'Failed',
          error: errorEl?.textContent?.trim() || 'Run failed',
        };
      }
      return null;
    },
    { timeout: config.timeoutMs }
  );

  const resolved = await outcome.jsonValue();
  const screenshotPath = `/Users/willem/Development/news_app/.tmp/${name}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: true });

  if (resolved.error) {
    return {
      name,
      ok: false,
      error: resolved.error,
      screenshotPath,
    };
  }

  await expect(page.locator('#result-summary')).toBeVisible();
  const summaryText = await page.locator('#result-summary').innerText();
  const itemCount = await page.locator('#result-items > div').count();
  const failedCount = await page.locator('#result-items details').count();

  return {
    name,
    ok: true,
    summaryText,
    itemCount,
    failedCount,
    screenshotPath,
  };
}

test.describe.configure({ mode: 'serial' });

test('admin eval UI runs end to end', async ({ page }) => {
  test.setTimeout(420000);

  const results = [];
  results.push(
    await runEval(page, 'eval-cross-type-haiku', {
      contentTypes: ['article', 'podcast', 'news'],
      models: ['haiku'],
      recentPoolSize: 50,
      sampleSize: 3,
      seed: 42,
      timeoutMs: 180000,
    })
  );
  results.push(
    await runEval(page, 'eval-news-gpt52', {
      contentTypes: ['news'],
      models: ['gpt_5_2'],
      recentPoolSize: 50,
      sampleSize: 1,
      seed: 7,
      timeoutMs: 180000,
    })
  );

  fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));

  for (const result of results) {
    expect(result.ok, `${result.name} failed: ${result.error || 'unknown error'}`).toBe(true);
  }
});
