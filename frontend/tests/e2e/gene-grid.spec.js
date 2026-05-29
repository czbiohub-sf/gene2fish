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

function svgImage(label) {
  const encoded = label.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&apos;",
  })[c]);
  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="240" height="180" viewBox="0 0 240 180">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="#dbeafe"/>
          <stop offset="1" stop-color="#fde68a"/>
        </linearGradient>
      </defs>
      <rect width="240" height="180" fill="url(#bg)"/>
      <ellipse cx="120" cy="92" rx="72" ry="44" fill="#ffffff" opacity="0.72"/>
      <circle cx="82" cy="84" r="14" fill="#4338ca"/>
      <path d="M98 88 C130 42, 166 50, 184 82 C158 74, 132 80, 112 112" fill="none" stroke="#7c3aed" stroke-width="9" stroke-linecap="round"/>
      <text x="120" y="154" text-anchor="middle" font-family="monospace" font-size="16" font-weight="700" fill="#111827">${encoded}</text>
    </svg>
  `;
}

async function mockApi(page) {
  await page.route("**/api/stages", async (route) => {
    await route.fulfill({ json: stages });
  });

  await page.route("**/api/genes/search**", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q")?.toLowerCase() || "";
    const genes = ["pacsin2", "pax2a", "evx1"].filter((g) => g.startsWith(q));
    await route.fulfill({ json: genes });
  });

  await page.route("**/api/anatomy/search**", async (route) => {
    await route.fulfill({ json: ["hindbrain"] });
  });

  await page.route("**/api/anatomy/hindbrain/genes**", async (route) => {
    await route.fulfill({
      json: {
        total: 1,
        genes: [{ gene_symbol: "evx1", image_count: 36 }],
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
      } else {
        response[gene] = [];
      }
    }
    await route.fulfill({ json: response });
  });

  await page.route("https://images.example.test/**", async (route) => {
    const id = route.request().url().split("/").pop()?.replace(".png", "") || "mock-image";
    await route.fulfill({
      contentType: "image/svg+xml",
      body: svgImage(id),
    });
  });
}

test.beforeEach(async ({ page }) => {
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

  await expect(anatomyInput).toHaveValue("hindbrain");
  await expect(dropdown).toHaveCount(0);
  await expect(page.getByText("Genes with expression in")).toBeVisible();
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

  await expect(
    page.getByText("Enter a gene symbol above to start browsing expression images.")
  ).toBeVisible();
  await expect(page.locator(".expression-grid")).toHaveCount(0);
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
