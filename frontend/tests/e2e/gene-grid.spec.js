import { expect, test } from "@playwright/test";

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
    gene_symbol: gene,
    stage_name: stage.stage_name,
    stage_begin_hours: stage.begin_hours,
    stage_display_label: stage.display_label,
    anatomy_names: gene === "evx1" ? ["hindbrain"] : [],
    image_preparation: "whole-mount",
    figure_id: `FIG-${id}`,
    fish_name: "wild type",
    human_orthologs: [],
    disease_associations: [],
    uniprot_ids: [],
    publication_id: "ZDB-PUB-040907-1",
    pubmed_id: "123456",
    est_symbol: null,
    probe_quality: null,
  };
}

function imagesFor(gene, nPerStage = 1, selectedStages = stages) {
  return selectedStages.flatMap((stage) =>
    Array.from({ length: nPerStage }, (_, i) => image(gene, stage, i + 1))
  );
}

const MOCK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>';

async function mockApi(page) {
  await page.route("**/api/stages", async (route) => {
    await route.fulfill({ json: stages });
  });

  await page.route("**/api/genes/search**", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q")?.toLowerCase() || "";
    const genes = ["pacsin2", "pax2a", "evx1", "shhb", "nr5a2", "prox1a", "hand2"].filter((g) => g.startsWith(q));
    await route.fulfill({ json: genes });
  });

  await page.route("**/api/anatomy/search**", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q")?.toLowerCase() || "";
    const anatomyTerms = ["heart", "hindbrain", "liver primordium", "pronephros"];
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
      contentType: "image/svg+xml",
      body: MOCK_SVG,
    });
  });
}

test.beforeEach(async ({ page }) => {
  // Clear any handlers from a prior attempt so retries don't stack duplicate
  // routes on a reused page.
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page);
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
  await expect(page.getByText("Enter a gene name and select filters")).toBeVisible();
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
  // Override the image host so primary AND fallback URLs both fail, exercising
  // SingleCell's two-step fallback (image_url -> image_url_fallback -> placeholder).
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
