import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const stages = [
  { stage_name: "Gastrula:50%-epiboly", begin_hours: 5.25, display_label: "50%-epiboly" },
  { stage_name: "Segmentation:1-4 somites", begin_hours: 10.33, display_label: "1-4 somites" },
  { stage_name: "Segmentation:14-19 somites", begin_hours: 16, display_label: "14-19 somites" },
  { stage_name: "Segmentation:20-25 somites", begin_hours: 19, display_label: "20-25 somites" },
  { stage_name: "Pharyngula:Prim-15", begin_hours: 30, display_label: "Prim-15 (30 hpf)" },
  { stage_name: "Pharyngula:High-pec", begin_hours: 42, display_label: "High-pec (42 hpf)" },
];

function image(gene, stage, index = 1) {
  const id = `ZDB-IMAGE-${gene}-${stage.begin_hours}-${index}`.replaceAll(".", "-");
  return {
    image_id: id,
    image_url: `https://images.example.test/${id}.png`,
    image_url_fallback: `https://images.example.test/${id}-fallback.png`,
    image_thumb_url: `https://images.example.test/${id}-thumb.png`,
    gene_symbol: gene,
    gene_id: gene === "pax2a" ? "ZDB-GENE-040426-2596" : `ZDB-GENE-${gene}`,
    gene_name: gene === "pax2a" ? "paired box 2a" : `${gene} gene`,
    stage_name: stage.stage_name,
    stage_begin_hours: stage.begin_hours,
    stage_display_label: stage.display_label,
    anatomy_terms: gene === "evx1"
      ? [{ anatomy_name: "hindbrain", anatomy_id: "ZFA:0000125" }]
      : [],
    image_preparation: "whole-mount",
    figure_id: `FIG-${id}`,
    fish_name: "wild type",
    human_orthologs: gene === "pax2a"
      ? [{ human_symbol: "P2RX4", human_name: "purinergic receptor P2X 4" }]
      : [],
    disease_associations: [],
    uniprot_ids: gene === "pax2a" ? ["Q98TZ0"] : [],
    publication_id: "ZDB-PUB-040907-1",
    pubmed_id: "123456",
    est_id: gene === "pax2a" ? "ZDB-CDNA-040425-55286" : null,
    est_symbol: gene === "pax2a" ? "MGC:55286" : null,
    probe_quality: null,
  };
}

function imagesFor(gene, nPerStage = 1, selectedStages = stages) {
  return selectedStages.flatMap((stage) =>
    Array.from({ length: nPerStage }, (_, i) => image(gene, stage, i + 1))
  );
}

const MOCK_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64"
);

async function mockApi(page) {
  await page.route("**/api/stages", async (route) => {
    await route.fulfill({ json: stages });
  });

  await page.route("**/api/genes/search**", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q")?.toLowerCase() || "";
    const symbols = ["pacsin2", "pax2a", "evx1", "shhb", "nr5a2", "prox1a", "hand2"];
    // Previous/alias name → canonical symbol (mirrors the backend alias index).
    const aliases = { paxprev: "pax2a" };
    const results = symbols
      .filter((g) => g.startsWith(q))
      .map((symbol) => ({ symbol, matched_alias: null }));
    const seen = new Set(results.map((r) => r.symbol));
    for (const [alias, symbol] of Object.entries(aliases)) {
      if (alias.startsWith(q) && !seen.has(symbol)) {
        results.push({ symbol, matched_alias: alias });
        seen.add(symbol);
      }
    }
    await route.fulfill({ json: results });
  });

  await page.route("**/api/genes/*/resolve", async (route) => {
    // Mirrors the backend resolver: exact/case-insensitive symbol or a known
    // previous/alias name resolves to the canonical symbol; anything else 404s.
    const symbols = ["pacsin2", "pax2a", "evx1", "shhb", "nr5a2", "prox1a", "hand2"];
    const aliases = { paxprev: "pax2a" };
    const path = new URL(route.request().url()).pathname;
    const typed = decodeURIComponent(path.split("/").slice(-2, -1)[0]).toLowerCase();
    const canonical = symbols.find((s) => s === typed)
      || (aliases[typed] ? aliases[typed] : null);
    if (canonical) {
      await route.fulfill({
        json: { symbol: canonical, matched_alias: aliases[typed] ? typed : null },
      });
    } else {
      await route.fulfill({ status: 404, json: { detail: `No gene matching '${typed}'` } });
    }
  });

  await page.route("**/api/anatomy/search**", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q")?.toLowerCase() || "";
    const anatomyTerms = ["heart", "hindbrain", "liver primordium", "optic tectum neuropil region", "pronephros"];
    await route.fulfill({ json: anatomyTerms.filter((term) => term.includes(q)) });
  });

  await page.route("**/api/anatomy/*/genes**", async (route) => {
    await route.fulfill({
      json: {
        total: 0,
        genes: [],
      },
    });
  });

  await page.route("**/api/anatomy/hindbrain/genes**", async (route) => {
    await route.fulfill({
      json: {
        total: 1,
        genes: [{ gene_symbol: "evx1", image_count: 36 }],
      },
    });
  });

  await page.route("**/api/anatomy/liver%20primordium/genes**", async (route) => {
    await route.fulfill({
      json: {
        total: 2,
        genes: [
          { gene_symbol: "nr5a2", image_count: 12 },
          { gene_symbol: "prox1a", image_count: 9 },
        ],
      },
    });
  });

  await page.route("**/api/anatomy/genes**", async (route) => {
    const params = new URL(route.request().url()).searchParams;
    const terms = params.getAll("anatomy").sort();
    if (terms.join("|") === "heart|pronephros") {
      await route.fulfill({
        json: {
          total: 1,
          genes: [{ gene_symbol: "hand2", image_count: 18 }],
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        total: 0,
        genes: [],
      },
    });
  });

  // Default facets: every stage and anatomy term has images, so no filter
  // option is disabled. Tests that exercise the greying-out behavior override
  // this route with a restricted set.
  await page.route("**/api/genes/facets", async (route) => {
    await route.fulfill({
      json: {
        stages: stages.map((s) => ({ begin_hours: s.begin_hours, image_count: 5 })),
        anatomy: {
          heart: 4,
          hindbrain: 3,
          "liver primordium": 2,
          "optic tectum neuropil region": 1,
          pronephros: 6,
        },
      },
    });
  });

  await page.route("**/api/genes/batch", async (route) => {
    const body = route.request().postDataJSON();
    const response = {};
    for (const gene of body.genes) {
      if (gene === "pax2a") {
        response[gene] = imagesFor(gene, body.n_images || 1);
      } else if (gene === "pacsin2") {
        response[gene] = imagesFor(gene, 1, stages.slice(0, 5));
      } else if (gene === "evx1") {
        response[gene] = imagesFor(gene, 1, stages.slice(2, 6));
      } else if (gene === "shhb" || gene === "nr5a2" || gene === "prox1a" || gene === "hand2") {
        response[gene] = imagesFor(gene, 1, stages.slice(0, 3));
      } else {
        response[gene] = [];
      }
    }
    await route.fulfill({ json: response });
  });

  await page.route("https://images.example.test/**", async (route) => {
    await route.fulfill({
      contentType: "image/png",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: MOCK_PNG,
    });
  });
}

test.beforeEach(async ({ page }) => {
  // Clear any handlers from a prior attempt so retries don't stack duplicate
  // routes on a reused page.
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page);
});

test("primary nav links to ZebraHub", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: /ZebraHub/ })).toHaveAttribute(
    "href",
    "https://zebrahub.sf.czbiohub.org/"
  );
});

test("changing images per cell keeps queued image cells loading and clickable", async ({ page }) => {
  await page.goto("/?genes=pax2a");

  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length);

  await page.getByRole("button", { name: "3", exact: true }).click();

  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length * 3);
  const multiCell = page.locator(".image-cell.multi").first();
  await expect(multiCell).toBeVisible();
  const multiBox = await multiCell.boundingBox();
  expect(multiBox).not.toBeNull();
  const threeImageCellWidth = multiBox.width;

  await page.getByRole("button", { name: "1", exact: true }).click();

  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length);
  const singleCell = page.locator(".image-cell").first();
  await expect(singleCell).toBeVisible();
  const singleBox = await singleCell.boundingBox();
  expect(singleBox).not.toBeNull();
  const oneImageCellWidth = singleBox.width;
  expect(threeImageCellWidth).toBeGreaterThan(oneImageCellWidth * 2);

  await page.getByRole("button", { name: "6", exact: true }).click();
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length * 6);

  const firstImage = page.locator('img[alt^="pax2a at"]').first();
  await expect(firstImage).toBeVisible();
  await firstImage.click();
  await expect(page.locator(".lightbox-overlay")).toBeVisible();
  await expect(page.locator(".lightbox-title")).toHaveText("pax2a");
});

test("searching by a previous/alias name resolves to the canonical gene", async ({ page }) => {
  await page.goto("/");

  await page.getByPlaceholder("Gene symbol (e.g. pax2a)").fill("paxprev");

  // The dropdown surfaces the canonical symbol, annotated with the alias matched.
  const item = page.locator(".gene-input-wrapper .autocomplete-item", { hasText: "pax2a" });
  await expect(item).toBeVisible();
  await expect(item.locator(".autocomplete-alias")).toHaveText("a.k.a. paxprev");

  await item.click();

  // The canonical gene (not the typed alias) is added to the grid.
  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length);
});

test("rejects an invalid gene name instead of adding an empty column", async ({ page }) => {
  await page.goto("/");

  const input = page.getByPlaceholder("Gene symbol (e.g. pax2a)");
  await input.fill("notagene");
  await input.press("Enter");

  // An inline error appears and no comparison column is created.
  await expect(page.getByRole("alert")).toContainText('No gene matching "notagene"');
  await expect(page.getByRole("columnheader")).toHaveCount(0);
  await expect(page).not.toHaveURL(/genes=/);
});

test("validates a typed gene name and normalizes it to the canonical symbol", async ({ page }) => {
  await page.goto("/");

  const input = page.getByPlaceholder("Gene symbol (e.g. pax2a)");
  // Type a previous/alias name and submit without picking a suggestion; the
  // resolver normalizes it to the canonical symbol before opening the column.
  await input.fill("paxprev");
  await page.getByRole("button", { name: "Add" }).click();

  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await expect(page).toHaveURL(/genes=pax2a/);
  // The input clears and no error is shown on success.
  await expect(input).toHaveValue("");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a slow stale validation does not clobber a newer submission", async ({ page }) => {
  // First validation resolves slowly (and would 404); the user moves on before
  // it returns. The stale response must not surface an error or otherwise touch
  // state after the newer, valid submission succeeds.
  await page.route("**/api/genes/slowgene/resolve", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    // The page aborts this request when the user types a new value; fulfilling
    // an already-aborted route throws, which is irrelevant to the assertion.
    await route.fulfill({ status: 404, json: { detail: "No gene matching 'slowgene'" } }).catch(() => {});
  });

  await page.goto("/");
  const input = page.getByPlaceholder("Gene symbol (e.g. pax2a)");

  await input.fill("slowgene");
  await input.press("Enter"); // kicks off the slow validation

  // Move on to a valid gene before the slow request returns.
  await input.fill("pax2a");
  await page.getByRole("button", { name: "Add" }).click();

  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();

  // Wait past the slow request's completion; its stale 404 must be ignored —
  // no error banner, input stays cleared, no phantom column.
  await page.waitForTimeout(1300);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(input).toHaveValue("");
  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toHaveCount(1);
  await expect(page.getByRole("columnheader").filter({ hasText: "slowgene" })).toHaveCount(0);
});

test("shows no-image labels for empty cells in a mixed gene grid", async ({ page }) => {
  // The default batch mock returns [] for unrecognized gene symbols.
  await page.goto("/?genes=a1cf,pax2a");

  await expect(page.getByRole("columnheader").filter({ hasText: "a1cf" })).toBeVisible();
  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length);
  await expect(page.locator(".no-image-cell-text", { hasText: "No image" })).toHaveCount(stages.length);
  await expect(page.getByText("No expression images found for the selected genes and filters.")).toHaveCount(0);
});

test("lightbox links key metadata identifiers", async ({ page }) => {
  await page.goto("/?genes=pax2a");

  await page.locator('img[alt^="pax2a at"]').first().click();
  await expect(page.locator(".lightbox-overlay")).toBeVisible();

  const firstMetaGroup = page.locator(".lightbox-meta-col .meta-group").first();
  await expect(firstMetaGroup.locator(".meta-label")).toHaveText("Gene");
  await expect(firstMetaGroup).toContainText("paired box 2a");
  await expect(firstMetaGroup.getByRole("link", { name: "ZDB-GENE-040426-2596" })).toHaveAttribute(
    "href",
    "https://zfin.org/ZDB-GENE-040426-2596"
  );

  const firstImageId = "ZDB-IMAGE-pax2a-5-25-1";
  await expect(page.getByRole("link", { name: firstImageId })).toHaveAttribute(
    "href",
    `https://zfin.org/${firstImageId}`
  );
  await expect(page.getByRole("link", { name: "MGC:55286" })).toHaveAttribute(
    "href",
    "https://www.zfin.org/action/quicksearch/prototype?q=MGC%3A55286"
  );
  await expect(page.getByRole("link", { name: "Q98TZ0" })).toHaveAttribute(
    "href",
    "https://www.uniprot.org/uniparc?query=(dbid:Q98TZ0)"
  );
  await expect(page.getByRole("link", { name: "P2RX4" })).toHaveAttribute(
    "href",
    "https://www.ncbi.nlm.nih.gov/search/all/?term=P2RX4"
  );
});

test("lightbox shows anatomy terms with a ZFA id linked to ZFIN", async ({ page }) => {
  await page.goto("/?genes=evx1");

  await page.locator('img[alt^="evx1 at"]').first().click();
  await expect(page.locator(".lightbox-overlay")).toBeVisible();

  const anatomyGroup = page
    .locator(".lightbox-meta-col .meta-group")
    .filter({ has: page.locator(".meta-label", { hasText: "Anatomy" }) });
  await expect(anatomyGroup).toContainText("hindbrain");
  await expect(anatomyGroup.getByRole("link", { name: "ZFA:0000125" })).toHaveAttribute(
    "href",
    "https://zfin.org/ZFA:0000125"
  );
});

test("lightbox keeps the header fixed while the modal body scrolls", async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 460 });
  await page.route("**/api/genes/batch", async (route) => {
    const body = route.request().postDataJSON();
    const response = {};
    for (const gene of body.genes) {
      response[gene] = imagesFor(gene, body.n_images || 1).map((img) => ({
        ...img,
        uniprot_ids: Array.from({ length: 40 }, (_, i) => `Q98TZ${i}`),
        disease_associations: Array.from({ length: 10 }, (_, i) => ({
          do_term_id: `DOID:${i}`,
          do_term_name: `Disease association ${i}`,
        })),
      }));
    }
    await route.fulfill({ json: response });
  });

  await page.goto("/?genes=pax2a");
  await page.locator('img[alt^="pax2a at"]').first().click();
  await expect(page.locator(".lightbox-overlay")).toBeVisible();

  const header = page.locator(".lightbox-header");
  const body = page.locator(".lightbox-body");
  const scrollMetrics = await body.evaluate((el) => ({
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight,
  }));
  expect(scrollMetrics.scrollHeight).toBeGreaterThan(scrollMetrics.clientHeight);

  const before = await header.boundingBox();
  expect(before).not.toBeNull();
  await body.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  const scrolledTop = await body.evaluate((el) => el.scrollTop);
  expect(scrolledTop).toBeGreaterThan(0);
  const after = await header.boundingBox();
  expect(after).not.toBeNull();
  expect(after.y).toBeCloseTo(before.y, 0);
});

test("exports only the expression table as a PNG", async ({ page }) => {
  const proxiedUrls = [];

  await page.route("**/api/genes/batch", async (route) => {
    const body = route.request().postDataJSON();
    const response = {};
    for (const gene of body.genes) {
      response[gene] = imagesFor(gene, body.n_images || 1).map((img) => ({
        ...img,
        image_url: `https://zfin.org/imageLoadUp/2005/ZDB-PUB-051025-1/${img.image_id}_annot.jpg`,
        image_url_fallback: `https://zfin.org/imageLoadUp/2005/ZDB-PUB-051025-1/${img.image_id}.jpg`,
        image_thumb_url: `https://zfin.org/imageLoadUp/2005/ZDB-PUB-051025-1/${img.image_id}_thumb.jpg`,
      }));
    }
    await route.fulfill({ json: response });
  });

  await page.route("https://zfin.org/imageLoadUp/**", async (route) => {
    await route.fulfill({
      contentType: "image/png",
      body: MOCK_PNG,
    });
  });

  await page.route("**/api/image-proxy**", async (route) => {
    proxiedUrls.push(new URL(route.request().url()).searchParams.get("url"));
    await new Promise((resolve) => setTimeout(resolve, 50));
    await route.fulfill({
      contentType: "image/png",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: MOCK_PNG,
    });
  });

  await page.goto("/?genes=pax2a");

  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export table PNG" }).click();
  await expect(page.getByRole("progressbar", { name: "PNG export progress" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Exporting \d+%/ })).toBeDisabled();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toMatch(/^gene2fish-table-pax2a\.png$/);
  const path = await download.path();
  expect(path).toBeTruthy();
  const bytes = await readFile(path);
  expect([...bytes.slice(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  expect(proxiedUrls.length).toBeGreaterThan(0);
  expect(proxiedUrls[0]).toContain("https://zfin.org/imageLoadUp/");
});

test("adding an anatomy-suggested gene preserves previously visible gene columns", async ({ page }) => {
  const batchRequests = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/genes/batch")) {
      batchRequests.push(request.postDataJSON());
    }
  });

  await page.goto("/?genes=pacsin2");

  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();
  await expect(page.locator('img[alt^="pacsin2 at"]')).toHaveCount(5);

  await page.getByPlaceholder("e.g. hindbrain").fill("hindbrain");
  const anatomyDropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(anatomyDropdown).toBeVisible();
  await anatomyDropdown.getByText("hindbrain", { exact: true }).click();
  await expect(page.getByRole("button", { name: /evx1/ })).toBeVisible();

  await page.getByRole("button", { name: /evx1/ }).click();

  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();
  await expect(page.getByRole("columnheader").filter({ hasText: "evx1" })).toBeVisible();
  await expect(page.locator('img[alt^="pacsin2 at"]')).toHaveCount(5);
  await expect(page.locator('img[alt^="evx1 at"]')).toHaveCount(4);
  expect(batchRequests.at(-1)).toMatchObject({
    genes: ["pacsin2", "evx1"],
    anatomy: null,
  });
  // Anatomy must never leak into the batch payload — every request stays null.
  expect(batchRequests.length).toBeGreaterThan(0);
  for (const req of batchRequests) {
    expect(req.anatomy).toBeNull();
  }
  // Positive assertion that the grid rendered with exactly the two expected
  // gene columns. This replaces a weak `.grid-empty` toHaveCount(0) check that
  // would pass vacuously if the empty-state element were renamed.
  await expect(
    page.getByRole("columnheader").filter({ hasText: /pacsin2|evx1/ })
  ).toHaveCount(2);
});

test("anatomy autocomplete closes after selecting a term", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Find genes by anatomy")).toBeVisible();
  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  await anatomyInput.fill("hindbrain");

  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await page.locator(".anatomy-filter .autocomplete-item", { hasText: "hindbrain" }).click();

  await expect(anatomyInput).toHaveValue("");
  await expect(page.locator(".anatomy-term-chip", { hasText: "hindbrain" })).toBeVisible();
  await expect(dropdown).toHaveCount(0);
  await expect(page.getByText("Genes with expression in")).toBeVisible();
});

test("anatomy dropdown shows options on focus and filters while typing", async ({ page }) => {
  const anatomySearchRequests = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/anatomy/search")) {
      anatomySearchRequests.push(request.url());
    }
  });

  await page.goto("/");

  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await anatomyInput.click();

  await expect(dropdown).toBeVisible();
  await expect(dropdown.getByText("heart", { exact: true })).toBeVisible();
  await expect(dropdown.getByText("pronephros", { exact: true })).toBeVisible();
  expect(anatomySearchRequests.length).toBeGreaterThan(0);

  await anatomyInput.fill("hi");
  await expect(dropdown.getByText("hindbrain", { exact: true })).toBeVisible();
  await expect(dropdown.getByText("heart", { exact: true })).toHaveCount(0);
});

test("filter controls use short labels with full-value tooltips", async ({ page }) => {
  await page.goto("/?genes=pax2a");

  const stageSelects = page.locator(".stage-filter select");
  await expect(stageSelects.nth(0)).toHaveAttribute("title", "Gastrula:50%-epiboly");
  await expect(stageSelects.nth(1)).toHaveAttribute("title", "Pharyngula:High-pec (42 hpf)");

  const selectedStageText = await stageSelects.nth(0).evaluate((select) => select.selectedOptions[0].textContent);
  const selectedTimeText = await stageSelects.nth(1).evaluate((select) => select.selectedOptions[0].textContent);
  expect(selectedStageText).toBe("50%-epiboly");
  expect(selectedTimeText).toBe("High-pec (42 hpf)");

  await page.getByPlaceholder("e.g. hindbrain").fill("optic");
  const option = page.locator(".anatomy-filter .autocomplete-item", { hasText: "optic tectum neuropil region" });
  await expect(option).toHaveAttribute("title", "optic tectum neuropil region");
  await option.click();
  await expect(page.locator(".anatomy-term-chip", { hasText: "optic tectum neuropil region" })).toHaveAttribute(
    "title",
    "optic tectum neuropil region"
  );

  await expect(page.locator(".expression-grid-toolbar .n-images-label")).toHaveText("Images per cell");
  await expect(page.locator(".expression-grid-toolbar").getByRole("button", { name: "1", exact: true })).toHaveAttribute(
    "title",
    "1 image per cell"
  );
  await expect(page.locator(".expression-grid-toolbar").getByRole("button", { name: "3", exact: true })).toHaveAttribute(
    "title",
    "3 images per cell"
  );
});

test("filter controls stay inside the filter card at common viewport widths", async ({ page }) => {
  const widths = [2048, 1800, 1728, 1536, 1510, 1440, 1366, 1280, 1180, 1024, 768, 390];
  const singleRowLaptopWidths = new Set([1440, 1366, 1280]);

  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?genes=pax2a&stage_min=10.33&stage_max=120");
    await expect(page.locator(".filters-card")).toBeVisible();

    const layout = await page.evaluate(() => {
      const card = document.querySelector(".filters-card").getBoundingClientRect();
      const searchCard = document.querySelector(".search-card").getBoundingClientRect();
      const filtersCard = document.querySelector(".filters-card").getBoundingClientRect();
      const controls = [...document.querySelectorAll(".filters-grid > *")].map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          className: element.className,
          left: rect.left,
          right: rect.right,
          width: rect.width,
          top: rect.top,
        };
      });
      const selects = [...document.querySelectorAll(".stage-filter select")].map((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width;
      });

      return {
        cardLeft: card.left,
        cardRight: card.right,
        viewportWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        densityInFilters: document.querySelectorAll(".filters-grid .n-images-toggle").length,
        densityInToolbar: document.querySelectorAll(".expression-grid-toolbar .n-images-toggle").length,
        searchTop: searchCard.top,
        filtersTop: filtersCard.top,
        controls,
        selects,
      };
    });

    expect(layout.scrollWidth, `viewport ${width} should not create horizontal page overflow`).toBeLessThanOrEqual(
      layout.viewportWidth + 1
    );
    expect(layout.controls).toHaveLength(2);
    expect(layout.densityInFilters, `density controls should not be in the filter card at ${width}px`).toBe(0);
    expect(layout.densityInToolbar, `density controls should live in the grid toolbar at ${width}px`).toBe(1);

    for (const control of layout.controls) {
      expect(control.left, `${control.className} should not overflow left at ${width}px`).toBeGreaterThanOrEqual(
        layout.cardLeft - 1
      );
      expect(control.right, `${control.className} should not overflow right at ${width}px`).toBeLessThanOrEqual(
        layout.cardRight + 1
      );
      expect(control.width, `${control.className} should remain usable at ${width}px`).toBeGreaterThan(0);
    }

    for (const selectWidth of layout.selects) {
      expect(selectWidth, `stage select should remain usable at ${width}px`).toBeGreaterThanOrEqual(140);
    }

    if (singleRowLaptopWidths.has(width)) {
      const controlTops = layout.controls.map((control) => control.top);
      expect(
        Math.max(...controlTops) - Math.min(...controlTops),
        `filter controls should stay on one row at ${width}px`
      ).toBeLessThanOrEqual(1);
      expect(Math.abs(layout.searchTop - layout.filtersTop), `top cards should share a row at ${width}px`).toBeLessThanOrEqual(1);
    }
  }
});

test("anatomy clear button resets the input and hides suggested genes", async ({ page }) => {
  await page.goto("/");

  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  await anatomyInput.fill("hindbrain");
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("hindbrain", { exact: true }).click();

  await expect(page.locator(".suggested-genes-wrap")).toBeVisible();

  await page.locator(".anatomy-filter .anatomy-clear").click();

  await expect(anatomyInput).toHaveValue("");
  await expect(page.locator(".anatomy-term-chip", { hasText: "hindbrain" })).toHaveCount(0);
  await expect(page.locator(".suggested-genes-wrap")).toHaveCount(0);
});

test("shows error banner when the batch API fails, then clears on a successful refetch", async ({ page }) => {
  // Force the batch endpoint to fail. The default mock from beforeEach is
  // overridden here; the later-registered route wins in Playwright.
  let failBatch = true;
  await page.route("**/api/genes/batch", async (route) => {
    if (failBatch) {
      await route.fulfill({ status: 500, json: { detail: "boom" } });
      return;
    }
    const body = route.request().postDataJSON();
    const response = {};
    for (const gene of body.genes) {
      response[gene] = gene === "pax2a" ? imagesFor(gene, body.n_images || 1) : [];
    }
    await route.fulfill({ json: response });
  });

  await page.goto("/?genes=pax2a");

  await expect(page.getByText(/Error: API error: 500/)).toBeVisible();
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(0);

  // Recover: let the batch endpoint succeed and trigger a refetch by changing
  // images-per-cell (n_images is in useGeneData's dependency list).
  failBatch = false;
  await page.getByRole("button", { name: "3", exact: true }).click();

  await expect(page.getByText(/Error:/)).toHaveCount(0);
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length * 3);
});

test("shows the initial empty-state prompt when no genes are selected", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Search gene expression images" })).toBeVisible();
  await expect(page.getByText("Search one gene to explore its expression patterns")).toBeVisible();
  await expect(page.getByRole("button", { name: "Example: shhb" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Example: liver primordium" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Example: prox1a" })).toBeVisible();
  await expect(page.locator(".expression-grid")).toHaveCount(0);

  await page.getByRole("button", { name: "Example: liver primordium" }).click();
  await expect(page.locator(".anatomy-term-chip", { hasText: "liver primordium" })).toBeVisible();
  await expect(page.getByRole("columnheader").filter({ hasText: "nr5a2" })).toBeVisible();

  await page.goto("/");
  await page.getByRole("button", { name: "Example: shhb" }).click();
  await expect(page).toHaveURL(/genes=shhb/);
  await expect(page.getByRole("columnheader").filter({ hasText: "shhb" })).toBeVisible();
});

test("shows a no-results message for a gene with no matching images", async ({ page }) => {
  // The default batch mock returns [] for unrecognized gene symbols.
  await page.goto("/?genes=nosuchgene");

  await expect(
    page.getByText("No expression images found for the selected genes and filters.")
  ).toBeVisible();
  await expect(page.locator(".expression-grid")).toHaveCount(0);
});

test("shows 'Image unavailable' with a ZFIN link when both image URLs 404", async ({ page }) => {
  // Override the image host so the thumbnail AND fallback URLs both fail,
  // exercising SingleCell's fallback (image_thumb_url -> image_url_fallback ->
  // placeholder).
  await page.route("https://images.example.test/**", async (route) => {
    await route.fulfill({ status: 404 });
  });

  // Single image per cell (default) renders SingleCell, which wires onFail.
  await page.goto("/?genes=pax2a");

  const placeholder = page.locator(".cell-placeholder").first();
  await expect(placeholder).toBeVisible();
  await expect(placeholder.getByText("Image unavailable")).toBeVisible();

  const zfinLink = placeholder.getByRole("link");
  await expect(zfinLink).toHaveAttribute(
    "href",
    /^https:\/\/zfin\.org\/ZDB-IMAGE-pax2a/
  );

  // No usable images should remain rendered.
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(0);
});

test("narrowing the stage range refetches and shows only in-range stages", async ({ page }) => {
  const batchRequests = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/genes/batch")) {
      batchRequests.push(request.postDataJSON());
    }
  });

  // Override the batch mock to honor the requested stage range so the grid
  // reflects stage_min/stage_max (the default mock ignores them).
  await page.route("**/api/genes/batch", async (route) => {
    const body = route.request().postDataJSON();
    const lo = body.stage_min ?? -Infinity;
    const hi = body.stage_max ?? Infinity;
    const inRange = stages.filter((s) => s.begin_hours >= lo && s.begin_hours <= hi);
    await route.fulfill({
      json: { pax2a: imagesFor("pax2a", body.n_images || 1, inRange) },
    });
  });

  await page.goto("/?genes=pax2a");
  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(stages.length);

  // Pick stage_min = 10.33 and stage_max = 19 via the StageFilter selects
  // (begin_hours 10.33, 16, 19 are in range -> 3 stages).
  const selects = page.locator(".stage-filter select");
  await selects.nth(0).selectOption("10.33");
  await selects.nth(1).selectOption("19");

  await expect(page.locator('img[alt^="pax2a at"]')).toHaveCount(3);
  // Out-of-range stage rows are dropped; an in-range row remains.
  await expect(page.locator(".row-header", { hasText: "50%-epiboly" })).toHaveCount(0);
  await expect(page.locator(".row-header", { hasText: "1-4 somites" })).toBeVisible();

  const lastReq = batchRequests.at(-1);
  expect(lastReq).toMatchObject({ stage_min: 10.33, stage_max: 19 });
});

test("lightbox prev/next navigation respects boundary guards and close", async ({ page }) => {
  // Two genes so adjacent images in reading order span different gene symbols,
  // letting us observe the lightbox title change as we navigate.
  await page.goto("/?genes=pacsin2,evx1");

  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();
  await expect(page.locator(".cell-img").first()).toBeVisible();

  // Reading order starts at pacsin2 (top-left). Open the first image.
  await page.locator(".cell-img").first().click();
  const overlay = page.locator(".lightbox-overlay");
  await expect(overlay).toBeVisible();
  await expect(page.locator(".lightbox-title")).toHaveText("pacsin2");

  const prev = page.locator(".lightbox-nav-prev");
  const next = page.locator(".lightbox-nav-next");

  // First image: prev disabled, next enabled.
  await expect(prev).toBeDisabled();
  await expect(next).toBeEnabled();

  // Navigate forward until the title changes to the other gene.
  for (let i = 0; i < 10 && (await page.locator(".lightbox-title").textContent()) === "pacsin2"; i++) {
    await next.click();
  }
  await expect(page.locator(".lightbox-title")).toHaveText("evx1");

  // Walk to the last image; next becomes disabled at the boundary.
  for (let i = 0; i < 10 && (await next.isEnabled()); i++) {
    await next.click();
  }
  await expect(next).toBeDisabled();
  await expect(prev).toBeEnabled();

  // Close dismisses the overlay.
  await page.locator(".lightbox-close").click();
  await expect(overlay).toHaveCount(0);
});

test("suggested-gene chip disables after adding and the gene is not duplicated", async ({ page }) => {
  await page.goto("/?genes=pacsin2");

  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();

  await page.getByPlaceholder("e.g. hindbrain").fill("hindbrain");
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("hindbrain", { exact: true }).click();

  const chip = page.locator(".suggested-genes-strip .suggested-gene-chip", { hasText: "evx1" });
  await expect(chip).toBeVisible();
  await expect(chip).toBeEnabled();

  await chip.click();

  // The same chip is now disabled because evx1 is already a queried gene.
  await expect(chip).toBeDisabled();

  // evx1 is added exactly once — clicking again (or a dedup regression) must
  // not create a second column.
  await expect(page.getByRole("columnheader").filter({ hasText: "evx1" })).toHaveCount(1);
});

test("multiple anatomy terms show AND-matched suggested genes", async ({ page }) => {
  await page.goto("/");

  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  await anatomyInput.fill("heart");
  let dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("heart", { exact: true }).click();
  await expect(page.locator(".anatomy-term-chip", { hasText: "heart" })).toBeVisible();

  await anatomyInput.fill("pronephros");
  dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("pronephros", { exact: true }).click();

  await expect(page.locator(".anatomy-term-chip", { hasText: "pronephros" })).toBeVisible();
  await expect(page.getByText("Genes with expression in")).toBeVisible();
  await expect(page.getByText("heart AND pronephros")).toBeVisible();
  await expect(page.locator(".suggested-gene-chip", { hasText: "hand2" })).toBeVisible();
  await expect(page).toHaveURL(/anatomy=heart/);
  await expect(page).toHaveURL(/anatomy=pronephros/);
});

test("multiple anatomy terms with no shared genes still show the suggestions panel", async ({ page }) => {
  await page.goto("/");

  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  await anatomyInput.fill("heart");
  await page.getByRole("option", { name: "heart", exact: true }).click();

  await anatomyInput.fill("liver primordium");
  await page.getByRole("option", { name: "liver primordium", exact: true }).click();

  await expect(page.locator(".anatomy-term-chip", { hasText: "heart" })).toBeVisible();
  await expect(page.locator(".anatomy-term-chip", { hasText: "liver primordium" })).toBeVisible();
  await expect(page.locator(".suggested-genes-wrap")).toBeVisible();
  await expect(page.getByText("heart AND liver primordium")).toBeVisible();
  await expect(page.locator(".suggested-genes-empty")).toHaveText("No genes found.");
  await expect(page.locator(".suggested-gene-chip")).toHaveCount(0);
});

test("anatomy genes 404 silently shows no suggested-genes strip", async ({ page }) => {
  // Override the default valid stub so the genes endpoint 404s.
  await page.route("**/api/anatomy/*/genes**", async (route) => {
    await route.fulfill({ status: 404 });
  });

  await page.goto("/");
  await page.getByPlaceholder("e.g. hindbrain").fill("hindbrain");
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("hindbrain", { exact: true }).click();

  // 404 -> suggestions empty, no error -> the strip is not rendered.
  await expect(page.locator(".suggested-genes-wrap")).toHaveCount(0);
  await expect(page.locator(".suggested-genes-error")).toHaveCount(0);
});

test("anatomy genes 500 surfaces an error in the suggested-genes header", async ({ page }) => {
  await page.route("**/api/anatomy/*/genes**", async (route) => {
    await route.fulfill({ status: 500, json: { detail: "boom" } });
  });

  await page.goto("/");
  await page.getByPlaceholder("e.g. hindbrain").fill("hindbrain");
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("hindbrain", { exact: true }).click();

  // A non-404 failure renders the error span inside the strip header.
  await expect(page.locator(".suggested-genes-error")).toBeVisible();
  await expect(page.locator(".suggested-genes-error")).toContainText("Error:");
});

test("stage options disable for stages with no images, and re-enable when the gene is removed", async ({ page }) => {
  // pacsin2 only has images at the three earliest stages; the later three
  // should be greyed out and unselectable while it is the only gene.
  await page.route("**/api/genes/facets", async (route) => {
    const { genes } = route.request().postDataJSON();
    const enabled = genes.includes("pax2a")
      ? stages
      : stages.slice(0, 3); // pacsin2-only → early stages only
    await route.fulfill({
      json: {
        stages: enabled.map((s) => ({ begin_hours: s.begin_hours, image_count: 5 })),
        anatomy: { hindbrain: 3 },
      },
    });
  });

  await page.goto("/?genes=pacsin2");
  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();

  const stageSelect = page.locator(".stage-filter select").first();
  // In-range stage stays selectable; an out-of-range stage is disabled with a
  // hint. (toHaveJSProperty reads option.disabled directly — Playwright's
  // toBeDisabled is unreliable on <option> elements.)
  await expect(stageSelect.locator('option[value="5.25"]')).toHaveJSProperty("disabled", false);
  const disabledOption = stageSelect.locator('option[value="42"]');
  await expect(disabledOption).toHaveJSProperty("disabled", true);
  await expect(disabledOption).toHaveAttribute("title", "No images for the genes in the comparison");

  // Add pax2a (which covers every stage) → union re-enables the late stages.
  await page.getByPlaceholder("Gene symbol (e.g. pax2a)").fill("pax2a");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await expect(stageSelect.locator('option[value="42"]')).toHaveJSProperty("disabled", false);

  // Remove every gene → facets clear → all stages enabled again (original behavior).
  await page.getByTitle("Remove pax2a").click();
  await page.getByTitle("Remove pacsin2").click();
  await expect(page.getByRole("columnheader")).toHaveCount(0);
  await expect(stageSelect.locator('option[value="42"]')).toHaveJSProperty("disabled", false);
});

test("anatomy terms not expressed by the current genes are disabled with a hint", async ({ page }) => {
  // Only hindbrain has images for the gene in the grid; heart/pronephros are
  // de-emphasized (disabled) but still listed so the vocabulary stays visible.
  await page.route("**/api/genes/facets", async (route) => {
    await route.fulfill({
      json: {
        stages: stages.map((s) => ({ begin_hours: s.begin_hours, image_count: 5 })),
        anatomy: { hindbrain: 7 },
      },
    });
  });

  await page.goto("/?genes=pacsin2");
  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();

  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  await anatomyInput.click();
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();

  // Expressed term: enabled, annotated with its match count.
  const hindbrain = dropdown.locator(".autocomplete-item", { hasText: "hindbrain" });
  await expect(hindbrain).not.toHaveClass(/disabled/);
  await expect(hindbrain.locator(".autocomplete-count")).toHaveText("7");

  // Unexpressed term: disabled, aria-disabled, hint on hover, and unselectable.
  const heart = dropdown.locator(".autocomplete-item", { hasText: "heart" });
  await expect(heart).toHaveClass(/disabled/);
  await expect(heart).toHaveAttribute("aria-disabled", "true");
  await expect(heart).toHaveAttribute("title", "No images for the genes in the comparison");
  // force past the actionability check (the element is intentionally disabled)
  // to prove that even a click cannot select a de-emphasized term.
  await heart.click({ force: true });
  await expect(page.locator(".anatomy-term-chip", { hasText: "heart" })).toHaveCount(0);

  // The expressed term can still be selected.
  await hindbrain.click();
  await expect(page.locator(".anatomy-term-chip", { hasText: "hindbrain" })).toBeVisible();
});

test("with no genes in the comparison every anatomy option stays enabled", async ({ page }) => {
  await page.goto("/");

  const anatomyInput = page.getByPlaceholder("e.g. hindbrain");
  await anatomyInput.click();
  const dropdown = page.locator(".anatomy-filter .autocomplete-dropdown");
  await expect(dropdown).toBeVisible();

  // No genes → no facets request → nothing disabled, no counts shown.
  await expect(dropdown.locator(".autocomplete-item.disabled")).toHaveCount(0);
  await expect(dropdown.locator(".autocomplete-count")).toHaveCount(0);
});
