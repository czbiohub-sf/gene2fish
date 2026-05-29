import { expect, test } from "@playwright/test";

const png1x1 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";

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
      if (body.anatomy && gene === "pacsin2") {
        response[gene] = [];
      } else if (gene === "pax2a") {
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
    await route.fulfill({
      contentType: "image/png",
      body: Buffer.from(png1x1, "base64"),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("changing images per cell keeps queued image cells loading and clickable", async ({ page }) => {
  await page.goto("/?genes=pax2a");

  await expect(page.getByRole("columnheader").filter({ hasText: "pax2a" })).toBeVisible();
  await page.getByRole("button", { name: "3", exact: true }).click();

  await expect(page.locator(".cell-img")).toHaveCount(stages.length * 3);
  await expect(page.locator(".single-image-placeholder")).toHaveCount(0);

  await page.getByRole("button", { name: "1", exact: true }).click();

  await expect(page.locator(".cell-img")).toHaveCount(stages.length);
  await expect(page.locator(".single-image-placeholder")).toHaveCount(0);

  await page.getByRole("button", { name: "6", exact: true }).click();
  const firstQueuedOrLoadedImage = page.locator(".single-image-placeholder, .cell-img").first();
  await expect(firstQueuedOrLoadedImage).toBeVisible();
  await firstQueuedOrLoadedImage.click();
  await expect(page.locator(".lightbox-overlay")).toBeVisible();
});

test("adding an anatomy-suggested gene preserves previously visible gene columns", async ({ page }) => {
  await page.goto("/?genes=pacsin2");

  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();
  await expect(page.locator(".cell-img")).toHaveCount(5);

  await page.getByPlaceholder("e.g. hindbrain").fill("hindbrain");
  await page.getByText("hindbrain", { exact: true }).click();
  await expect(page.getByRole("button", { name: /evx1/ })).toBeVisible();

  await page.getByRole("button", { name: /evx1/ }).click();

  await expect(page.getByRole("columnheader").filter({ hasText: "pacsin2" })).toBeVisible();
  await expect(page.getByRole("columnheader").filter({ hasText: "evx1" })).toBeVisible();
  await expect(page.locator(".cell-img")).toHaveCount(9);
  await expect(page.locator(".grid-empty")).toHaveCount(0);
});
