// Optional browser smoke checks. Run against local HTTP previews with Playwright installed.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.OBSERVATORY_PLAYWRIGHT || "playwright");

async function run() {
  const [publicUrl, privateUrl] = process.argv.slice(2);
  assert(publicUrl, "Supply the public demo preview URL and optionally the private app URL.");
  const browser = await chromium.launch({
    ...(process.env.OBSERVATORY_BROWSER_EXE ? { executablePath: process.env.OBSERVATORY_BROWSER_EXE } : {}),
  });
  try {
    const publicPage = await browser.newPage({viewport: {width: 1280, height: 920}});
    const errors = [];
    publicPage.on("pageerror", error => errors.push(error.message));
    const requests = [];
    publicPage.on("request", request => requests.push(request.url()));
    await publicPage.goto(publicUrl);
    await publicPage.locator("#data-scope").getByText(/Public demo/).waitFor();
    await publicPage.getByRole("button", {name: "Demo bus corridor", exact: true}).waitFor();
    await publicPage.locator("#filters select[name=mode]").selectOption("PUB");
    await publicPage.locator("#filters select[name=classification]").selectOption("IRIP");
    await publicPage.getByRole("button", {name: "Apply filters"}).click();
    assert.equal(await publicPage.locator("#record-count").textContent(), "1");
    await publicPage.locator("#area-panel").evaluate(e => e.open = true);
    await publicPage.locator("#area-panel details").evaluate(e => e.open = true);
    await publicPage.getByLabel("Area bounds").fill("125.585,7.083,125.595,7.09");
    await publicPage.getByRole("button", {name: "Compare area"}).click();
    await publicPage.getByText(/^1 documented lines intersecting this area/).waitFor();
    await publicPage.getByLabel("Area bounds").fill("125.58,7.108,125.59,7.11");
    await publicPage.getByRole("button", {name: "Compare area"}).click();
    await publicPage.getByText("No documented lines intersect the selected area under these filters.").waitFor();
    await publicPage.getByLabel("Area bounds").fill("126,8,125,7");
    await publicPage.getByRole("button", {name: "Compare area"}).click();
    await publicPage.getByRole("status").getByText("Use ordered longitude and latitude values.").waitFor();
    await publicPage.getByLabel("Route search").fill("no such route");
    await publicPage.getByRole("button", {name: "Apply filters"}).click();
    await publicPage.getByText("No route records match.", {exact: true}).waitFor();
    await publicPage.getByLabel("Route search").fill("");
    await publicPage.getByRole("button", {name: "Apply filters"}).click();
    await selectFirstMapLine(publicPage);
    await save(publicPage, "Synthetic browser review example");
    await publicPage.reload();
    await publicPage.getByRole("button", {name: "Demo bus corridor", exact: true}).click();
    await publicPage.getByRole("button", {name: "Open case: unresolved geometry association"}).click();
    await publicPage.locator("#history").getByText(/Synthetic browser review example/).waitFor();
    assert.deepEqual(errors, []);
    assert(requests.every(url => new URL(url).origin === new URL(publicUrl).origin && !new URL(url).pathname.startsWith("/api/")));
    if (process.env.OBSERVATORY_SCREENSHOTS) await publicPage.screenshot({path: process.env.OBSERVATORY_SCREENSHOTS + '/desktop.png', fullPage:true});
    await publicPage.getByRole('button', {name:'Network X-Ray',exact:true}).click();
    await publicPage.getByRole('button', {name:'Clear filters',exact:true}).click();
    await publicPage.getByLabel('Map evidence',{exact:true}).selectOption('missing');
    await publicPage.getByRole('button',{name:'Apply filters'}).click();
    assert.equal(await publicPage.locator('#record-count').textContent(),'1');
    assert.equal(await publicPage.evaluate(()=>state.features.length),0);
    await publicPage.getByRole('button', {name:'Demo record awaiting linework',exact:true}).click();
    await publicPage.getByText(/^No map geometry associated/).waitFor();
    await publicPage.getByRole('button', {name:'Zoom to selection',exact:true}).click();
    await publicPage.getByText('The selected record has no displayed map geometry.').waitFor();
    await publicPage.getByRole('button',{name:'Clear filters',exact:true}).click();
    await publicPage.getByRole('button', {name:'Demo jeepney corridor',exact:true}).click();
    await publicPage.getByRole('button', {name:'Zoom in',exact:true}).click();
    await publicPage.locator('#map').focus();
    await publicPage.keyboard.press('ArrowRight');
    await publicPage.getByRole('button', {name:'Fit network',exact:true}).click();
    await publicPage.getByRole('button',{name:'Select area',exact:true}).click();
    const box=await publicPage.locator('#map').boundingBox();
    await publicPage.mouse.move(box.x+20,box.y+20); await publicPage.mouse.down();
    await publicPage.mouse.move(box.x+box.width-20,box.y+box.height-20,{steps:5}); await publicPage.mouse.up();
    await publicPage.getByText(/^3 documented lines intersecting this area/).waitFor();
    await publicPage.getByRole('button',{name:'Clear area',exact:true}).click();
    await publicPage.getByRole('button',{name:'Pan / select',exact:true}).click();
    await publicPage.setViewportSize({width: 390, height: 844});
    assert(await publicPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await publicPage.getByRole('button', {name:'Map',exact:true}).click();
    if (process.env.OBSERVATORY_SCREENSHOTS) await publicPage.screenshot({path: process.env.OBSERVATORY_SCREENSHOTS + '/narrow-map.png',fullPage:true});
    await publicPage.getByRole('button', {name:'Inspect',exact:true}).click();
    await save(publicPage, 'Narrow layout keyboard review');
    if (process.env.OBSERVATORY_SCREENSHOTS) await publicPage.screenshot({path: process.env.OBSERVATORY_SCREENSHOTS + '/narrow-review.png',fullPage:true});
    assert(await publicPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    console.log("Public browser checks passed: filters, intersecting/missing/invalid area, map selection, browser-local persistence, narrow layout and no API requests.");

    if (privateUrl) {
      const privatePage = await browser.newPage();
      privatePage.on("pageerror", error => errors.push(error.message));
      await privatePage.goto(privateUrl);
      await privatePage.locator("#release").waitFor({state:"attached"});
      await privatePage.waitForFunction(() => document.querySelector("#record-count").textContent.trim() !== "");
      const routeId = await privatePage.evaluate(async () => {
        for (let offset = 0; offset < 1000; offset += 100) {
          const result = await fetch("/api/cases?limit=100&offset=" + offset).then(response => response.json());
          for (const item of result.items) {
            const features = await fetch("/api/features?limit=1&q=" + encodeURIComponent(item.route_id)).then(response => response.json());
            if (features.total) return item.route_id;
          }
          if (offset + 100 >= result.total) break;
        }
        return null;
      });
      assert(routeId, "No unresolved case linked to a displayed source line.");
      await privatePage.getByLabel("Route search").fill(routeId);
      await privatePage.getByRole("button", {name: "Apply filters"}).click();
      await privatePage.waitForFunction(() => document.querySelector("#record-count").textContent === "1");
      await selectFirstMapLine(privatePage);
      await save(privatePage, "Local browser QA decision");
      await privatePage.getByText("Project decision saved to local SQLite history.").waitFor();
      await privatePage.route('**/api/cases/*/reviews', route => route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Test save failure'})}));
      await privatePage.getByLabel('Evidence note').fill('Keep this note after failure');
      await privatePage.getByRole('button',{name:'Save project review',exact:true}).click();
      await privatePage.getByText('Test save failure').waitFor();
      assert.equal(await privatePage.getByLabel('Evidence note').inputValue(),'Keep this note after failure');
      await privatePage.unroute('**/api/cases/*/reviews');
      await privatePage.route('**/api/health',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Release verification failed; app unavailable'})}));
      await privatePage.reload();
      await privatePage.getByText('Release verification failed; app unavailable').waitFor();
      assert.deepEqual(errors, []);
      console.log("Private browser checks passed: real map selection, unresolved case evidence and SQLite form write.");
    }
  } finally {
    await browser.close();
  }
}

async function selectFirstMapLine(page) {
  // Read the rendered map transform and click on a real screen-space line segment.
  const position = await page.evaluate(() => {
    const feature = state.features[0];
    const line = lines(feature)[0];
    const index = Math.floor((line.length - 1) / 2);
    const [x, y] = state.active.project(line[index]);
    return {x, y};
  });
  await page.locator("#map").click({position});
}

async function save(page, note) {
  await page.getByRole("button", {name: "Open case: unresolved geometry association"}).first().click();
  await page.getByLabel("Reviewer name or alias").fill("Browser QA");
  await page.getByLabel("Evidence note").fill(note);
  await page.getByRole("button", {name: "Save project review"}).click();
  await page.locator("#history").getByText(new RegExp(note)).first().waitFor();
}

run().catch(error => { console.error(error); process.exitCode = 1; });
