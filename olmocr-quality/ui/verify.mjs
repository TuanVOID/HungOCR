import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
const require = createRequire(process.argv[2]);
const { chromium } = require("playwright");
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await mkdir(new URL("./review/", import.meta.url), { recursive: true });
await page.goto("http://127.0.0.1:8010");
await page.getByText("Server OCR sẵn sàng", { exact: true }).waitFor();
await page
  .locator("#file")
  .setInputFiles("F:/.VibeCoding/19.HungOCR/docling/docs/test_OCR.pdf");
await page.getByRole("button", { name: "Bắt đầu OCR", exact: true }).click();
await page.waitForFunction(
  () => !document.querySelector("#md").hidden,
  {},
  { timeout: 240000 },
);
const result = await page.locator("#result").textContent();
if (!result.includes("LUẬT") || !result.includes("Vương Đình Huệ"))
  throw new Error("Missing expected OCR text");
const download = page.waitForEvent("download");
await page.locator("#md").click();
await download;
await page.screenshot({
  path: new URL("./review/desktop.png", import.meta.url).pathname.replace(
    /^\/(\w:)/,
    "$1",
  ),
  fullPage: true,
});
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: new URL("./review/mobile.png", import.meta.url).pathname.replace(
    /^\/(\w:)/,
    "$1",
  ),
  fullPage: true,
});
if (
  await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
)
  throw new Error("Mobile horizontal overflow");
await page.reload();
await page.locator("#history button").first().click();
await page.locator("#result").waitFor({ state: "visible" });
console.log(
  JSON.stringify({
    textLength: result.length,
    browserErrors: errors,
    historyReload: true,
    download: true,
  }),
);
await browser.close();
if (errors.length) process.exitCode = 1;
