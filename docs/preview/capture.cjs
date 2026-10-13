const { chromium } = require("playwright");
let browser;
(async () => {
  browser = await chromium.launch({ channel: "chrome", headless: true });
  const page = await browser.newPage({
    viewport: { width: 1200, height: 1100 },
    deviceScaleFactor: 1.5,
    timezoneId: "Europe/Prague",
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.clock.install({ time: new Date("2026-10-13T14:00:00+02:00") });
  await page.goto("http://127.0.0.1:18765/docs/preview/");
  await page.waitForFunction(() =>
    document
      .querySelector("ids-jmk-map-card")
      ?.shadowRoot.querySelector(".status")
      ?.textContent.startsWith("2 vozidel"),
  );
  await page.waitForTimeout(2000);
  await page.locator("ids-jmk-alerts-card summary").click();
  await page.screenshot({
    path: "docs/screenshots/ha-dashboard.png",
    fullPage: true,
  });
  await page.locator("ids-jmk-map-card .vehicle").first().click();
  await page.waitForFunction(() =>
    document
      .querySelector("ids-jmk-map-card")
      .shadowRoot.querySelector(".detail")
      .textContent.includes("Česká"),
  );
  await page.locator("#map").evaluate((el) => {
    const label = document.createElement("p");
    label.textContent =
      "Ukázková data · skutečná karta v samostatném náhledu mimo HA";
    el.prepend(label);
  });
  await page
    .locator("#map")
    .screenshot({ path: "docs/screenshots/ha-map-detail.png" });
  await page.goto("http://127.0.0.1:18765/docs/preview/?dark");
  await page.setViewportSize({ width: 430, height: 1000 });
  await page.locator("ids-jmk-departures-card").first().waitFor();
  await page.waitForFunction(() =>
    document
      .querySelector("ids-jmk-map-card")
      ?.shadowRoot.querySelector(".status")
      ?.textContent.startsWith("2 vozidel"),
  );
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: "docs/screenshots/ha-mobile-dark.png",
    fullPage: true,
  });
  console.log(
    JSON.stringify({
      title: await page.title(),
      errors,
      overflow: await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    }),
  );
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw new Error("Náhled přetéká na mobilní šířce.");
  const fixture = await page.evaluate(() => window.docsFixture);
  await page.setViewportSize({ width: 1200, height: 1000 });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const stop = {
      id: "demo",
      name: "Brno, hlavní nádraží",
      directions: fixture.departures.map((d) => d.destination),
      lines: fixture.departures.map((d) => d.line),
      platforms: [],
    };
    const data = path.endsWith("/status")
      ? {
          ready: true,
          downloads: {
            gtfs: {
              enabled: true,
              last_downloaded_at: "2026-10-13T04:00:00+02:00",
              last_checked_at: "2026-10-13T04:00:00+02:00",
            },
            realtime: {
              enabled: true,
              last_downloaded_at: "2026-10-13T14:00:00+02:00",
              last_checked_at: "2026-10-13T14:00:00+02:00",
            },
          },
        }
      : path.endsWith("/departures")
        ? {
            ...fixture.attributes,
            stop,
            timezone: "Europe/Prague",
            previous_departures: [],
          }
        : stop;
    await route.fulfill({ json: data });
  });
  await page.goto("http://127.0.0.1:18766/?stop=demo");
  await page.locator("#departures tr").first().waitFor();
  await page.evaluate(() => {
    const label = document.createElement("p");
    label.textContent =
      "DOKUMENTACE · Ukázková data, nikoli aktuální jízdní řád";
    label.style =
      "background:#fff4cf;color:#664b00;padding:14px;text-align:center;margin:0;font:16px Arial";
    document.body.prepend(label);
  });
  await page.screenshot({
    path: "docs/screenshots/web-departures.png",
    fullPage: true,
  });
  await page.locator("#api-link").click();
  if (!(await page.locator("#api-dialog").isVisible()))
    throw new Error("Dialog API se neotevřel.");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("HA karty, detail mapy, mobilní šířka a webový dialog API: OK");
})()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await browser?.close();
  });
