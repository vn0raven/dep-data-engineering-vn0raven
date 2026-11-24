// Optional browser smoke checks. Run against local HTTP previews with Playwright installed.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.OBSERVATORY_PLAYWRIGHT || "playwright");

async function run() {
  const [publicUrl, privateUrl, proposalUrl] = process.argv.slice(2);
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
    const started=Date.now();
    await publicPage.goto(publicUrl);
    await publicPage.locator('#data-scope').getByText(/OSM/).waitFor();
    const loadMs=Date.now()-started;
    await publicPage.getByLabel('Source',{exact:true}).selectOption('OSM');
    await publicPage.getByRole('button',{name:'Apply filters'}).click();
    assert.equal(await publicPage.locator('#record-count').textContent(),'14');
    await publicPage.locator('#routes button').first().focus();
    await publicPage.keyboard.press('Enter');
    await publicPage.getByText('Explicit OSM relation membership.',{exact:true}).waitFor();
    const selected=await publicPage.evaluate(()=>state.selected);
    assert(selected.startsWith('osm-relation-'));
    await publicPage.getByRole('button',{name:'Zoom to selection',exact:true}).click();
    await selectFirstMapLine(publicPage);
    await publicPage.getByLabel('Route search').fill('no matching record');
    await publicPage.getByRole('button',{name:'Apply filters'}).click();
    assert.equal(await publicPage.locator('#record-count').textContent(),'0');
    await publicPage.getByRole('button',{name:'Clear filters',exact:true}).click();
    await publicPage.getByLabel('Source',{exact:true}).selectOption('OSM');
    await publicPage.getByRole('button',{name:'Apply filters'}).click();
    await publicPage.locator('#filters select[name=evidence]').selectOption('missing');
    await publicPage.getByRole('button',{name:'Apply filters'}).click();
    assert.equal(await publicPage.locator('#record-count').textContent(),'0');
    await publicPage.getByRole('button',{name:'Clear filters',exact:true}).click();
    await publicPage.getByLabel('Source',{exact:true}).selectOption('OSM');
    await publicPage.getByRole('button',{name:'Apply filters'}).click();
    await publicPage.locator('#area-panel').evaluate(e=>e.open=true);
    await publicPage.locator('#area-panel details').evaluate(e=>e.open=true);
    await publicPage.getByLabel('Area bounds').fill('120,0,130,20');
    await publicPage.getByRole('button',{name:'Compare area',exact:true}).click();
    await publicPage.getByText(/^14 documented lines intersecting this area/).waitFor();
    await publicPage.getByLabel('Area bounds').fill('130,20,120,0');
    await publicPage.getByRole('button',{name:'Compare area',exact:true}).click();
    await publicPage.getByText('Use ordered longitude and latitude values.',{exact:true}).waitFor();
    await publicPage.getByRole('button',{name:'Clear area',exact:true}).click();
    await publicPage.locator('#area-panel').evaluate(e=>e.open=false);
    await publicPage.locator('#routes button').first().click();
    await publicPage.locator('#map').focus();await publicPage.keyboard.press('ArrowRight');await publicPage.keyboard.press('+');
    await publicPage.getByRole('button',{name:'Zoom to selection',exact:true}).click();
    await publicPage.locator('.browse').evaluate(e=>e.scrollTop=0);
    const timing=await publicPage.evaluate(()=>{const start=performance.now();for(let i=0;i<10;i++)paint();return (performance.now()-start)/10});
    if(process.env.OBSERVATORY_SCREENSHOTS)await publicPage.screenshot({path:process.env.OBSERVATORY_SCREENSHOTS+'/osm-desktop.png',fullPage:true});
    await publicPage.setViewportSize({width:390,height:844});
    await publicPage.getByRole('button',{name:'Map',exact:true}).click();
    assert(await publicPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(process.env.OBSERVATORY_SCREENSHOTS)await publicPage.screenshot({path:process.env.OBSERVATORY_SCREENSHOTS+'/osm-phone.png',fullPage:true});
    await publicPage.getByRole('button',{name:'Inspect',exact:true}).click();
    await publicPage.getByText('Explicit OSM relation membership.',{exact:true}).waitFor();
    assert.deepEqual(errors,[]);
    assert(requests.every(url=>new URL(url).origin===new URL(publicUrl).origin&&!new URL(url).pathname.startsWith('/api/')));
    await publicPage.route('**/bundle.json',route=>route.fulfill({status:200,body:'{}'}));
    await publicPage.reload();await publicPage.getByText(/Release integrity failed/).waitFor();
    console.log(JSON.stringify({public:'passed',load_ms:loadMs,mean_paint_ms:timing,requests:requests.length}));

    if(proposalUrl){
      const proposal=await browser.newPage({viewport:{width:1440,height:1000}});
      await proposal.goto(proposalUrl);await proposal.locator('#data-scope').getByText(/OSM/).waitFor();
      assert.equal(await proposal.locator('#record-count').textContent(),'299');
      await proposal.getByLabel('Source',{exact:true}).selectOption('LTFRB');
      await proposal.getByRole('button',{name:'Apply filters'}).click();
      assert.equal(await proposal.locator('#record-count').textContent(),'285');
      const geo=await proposal.locator('#filters select[name=geography] option').nth(1).getAttribute('value');
      await proposal.getByLabel('Source geography',{exact:true}).selectOption(geo);
      await proposal.getByRole('button',{name:'Apply filters'}).click();
      assert(await proposal.evaluate(g=>state.routes.every(r=>r.geography.includes(g)),geo));
      await proposal.getByLabel('Source geography',{exact:true}).selectOption('');
      await proposal.locator('#filters select[name=classification]').selectOption('IRIP');
      await proposal.getByRole('button',{name:'Apply filters'}).click();
      assert.equal(await proposal.locator('#record-count').textContent(),'104');
      await proposal.locator('#filters select[name=evidence]').selectOption('missing');
      await proposal.getByRole('button',{name:'Apply filters'}).click();
      assert(await proposal.locator('#routes button').count()>0);
      await proposal.locator('#routes button').first().click();
      await proposal.getByText(/^No associated map geometry/).waitFor();
      await proposal.getByRole('button',{name:'Clear filters',exact:true}).click();
      await proposal.locator('#filters select[name=evidence]').selectOption('candidate');
      await proposal.getByRole('button',{name:'Apply filters'}).click();
      await proposal.locator('#routes button').first().click();
      await proposal.getByText('Candidate LTFRB direction matches only; not confirmed.',{exact:true}).waitFor();
      console.log('Proposal source, classification, missing geometry and candidate labels passed.');
      await proposal.close();
    }
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
