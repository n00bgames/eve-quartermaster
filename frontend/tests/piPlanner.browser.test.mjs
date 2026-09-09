// Start backend/tests/pi_planner_preview.py and tests/pi-planner/vite.config.mjs first.
// PLAYWRIGHT_MODULE may point to a preinstalled Playwright package; no live login is used.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const errors=[];
page.on("pageerror",e=>errors.push(e.message));
const output=process.env.PI_SCREENSHOT_DIR || "tests/artifacts/pi-planner";
await mkdir(output,{recursive:true});
try {
  await page.goto("http://127.0.0.1:18482/tests/pi-planner/index.html");
  await page.getByRole("heading",{name:"Plan your next PI operation"}).waitFor();
  await page.getByLabel("Scenario name",{exact:true}).fill("Browser-tested operation");
  await page.getByLabel("Optimize for").selectOption("quota");
  await page.getByLabel("Product 1",{exact:true}).selectOption("3645");
  await page.getByLabel("Units / week",{exact:true}).fill("20000");
  await page.getByLabel("Inputs",{exact:true}).selectOption("extract");
  await page.getByRole("button",{name:"Save scenario",exact:true}).click();
  await page.getByText("Scenario saved.",{exact:true}).waitFor();
  await page.getByRole("button",{name:"Fetch ESI prices & calculate"}).click();
  await page.getByRole("heading",{name:"Best plans found"}).waitFor({timeout:30000});
  await page.getByText("Weekly cost ledger",{exact:true}).waitFor();
  assert.equal(await page.locator('[role="alert"]').count(),0);
  await page.screenshot({path:path.join(output,"operation-desktop.png"),fullPage:true});
  const downloadWait=page.waitForEvent("download");
  await page.getByRole("button",{name:"Build & shopping CSV"}).click();
  const download=await downloadWait;
  assert.equal(download.suggestedFilename(),"eqm-pi-build-sheet.csv");
  await page.getByRole("button",{name:"Preview native template"}).first().click();
  await page.getByRole("heading",{name:"Native template workbench"}).waitFor();
  await page.getByText(/Clipboard structure and route connectivity validated/).waitFor();
  assert.equal(await page.locator(".pi-template-map circle").count()>2,true);
  await page.getByRole("button",{name:"Validate & preview"}).click();
  await page.screenshot({path:path.join(output,"template-desktop.png"),fullPage:true});
  await page.getByRole("button",{name:"Recipes & inventory",exact:true}).click();
  await page.getByRole("button",{name:"Use last observed colony inventory"}).click();
  await page.getByRole("button",{name:"Calculate batches & shopping"}).click();
  await page.getByText("Missing materials to purchase or extract",{exact:true}).waitFor();
  assert.equal(await page.locator(".pi-chain svg rect").count(),2);
  await page.getByLabel("Inspect chain item").selectOption("2268");
  await page.getByText(/Found on: Barren/).waitFor();
  await page.screenshot({path:path.join(output,"recipes-desktop.png"),fullPage:true});
  await page.route("**/api/planetary-industry/planner/regions",route=>route.fulfill({json:[{id:10000002,name:"The Forge"}]}));
  await page.route("**/api/planetary-industry/planner/systems?*",route=>route.fulfill({json:[{id:30000142,name:"Jita",security:.9}]}));
  await page.route("**/api/planetary-industry/planner/scout",route=>route.fulfill({json:{systems:[{system_id:30000142,name:"Jita",security:.9,score:1,planets:[{key:"40000001",name:"Test planet",planet_type:"Barren",planet_id:40000001,system_id:30000142,diameter_km:10000,security:.9,customs_percent:10,npc_tax_percent:10,yields:[],resource_type_ids:[2268]}],covered_resources:[2268],missing_resources:[]}],note:"Synthetic scouting data",as_of:"2026-09-09"}}));
  await page.getByRole("button",{name:"Scout planets",exact:true}).click();
  await page.getByLabel("Region",{exact:true}).selectOption("10000002");
  await page.getByLabel("Systems · choose up to 25").selectOption("30000142");
  await page.getByRole("button",{name:"Compare selected systems"}).click();
  await page.getByText("Jita · 1 planets · 1 matches",{exact:true}).click();
  await page.getByRole("button",{name:"Add these planets to scenario"}).click();
  await page.getByText(/Scouted planets added/).waitFor();
  await page.getByRole("button",{name:"Operation planner",exact:true}).click();
  await page.getByRole("button",{name:"Save changes",exact:true}).click();
  await page.getByText("Scenario saved.",{exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(output,"operation-mobile.png"),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);
  assert.equal(overflow,false,"Page should not overflow the mobile viewport");
  await page.getByRole("button",{name:"Delete saved copy",exact:true}).click();
  await page.getByText(/Saved scenario deleted/).waitFor();
  await page.reload();
  await page.getByText(/Recent runs \(/).click();
  await page.getByRole("button",{name:/Browser-tested operation · complete/}).first().click();
  await page.getByRole("heading",{name:"Best plans found"}).waitFor();
  if (process.env.EXPECT_PI_ENGINE) {
    await page.getByText("Constraints, provenance & search limits",{exact:true}).click();
    await page.getByText(`Allocation engine: ${process.env.EXPECT_PI_ENGINE}.`,{exact:true}).waitFor();
  }
  assert.deepEqual(errors,[]);
  process.stdout.write("Browser checks passed: saved scenario, calculation, build export, native template, recipe stock, scouting, mobile layout, deletion, run recovery, engine status.\n");
} finally {await browser.close();}
