"""API endpoint definitions."""

from __future__ import annotations

from collections import defaultdict
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query, Request

from .models import (
    AnatomyGene,
    AnatomyGenesResponse,
    BatchRequest,
    CanonicalStage,
    DiseaseAssociation,
    HumanOrtholog,
    ImageRecord,
)
from .stage_utils import CANONICAL_STAGES, get_stage_info, select_representative, select_top_n

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_image_url(pub_id: str, image_id: str) -> tuple[str, str]:
    """Return (annotated_url, plain_url) for an image."""
    # pub_id format: ZDB-PUB-YYMMDD-N  — year is "20" + first 2 chars of third segment
    # e.g. ZDB-PUB-010810-1 → "01" → "2001"
    try:
        year = "20" + pub_id.split("-")[2][:2]
    except (IndexError, AttributeError):
        year = "2000"
    base = f"https://zfin.org/imageLoadUp/{year}/{pub_id}/{image_id}"
    return f"{base}_annot.jpg", f"{base}.jpg"


def _record_to_model(record: dict) -> ImageRecord:
    """Convert a raw data record to an ImageRecord pydantic model."""
    image_id = record.get("image_id", "")
    pub = record.get("publication") or {}
    pub_id = pub.get("publication_id") or ""
    image_url, image_url_fallback = _build_image_url(pub_id, image_id)

    gene = record.get("gene") or {}
    image_info = record.get("image_info") or {}
    expression = record.get("expression") or {}
    fish = record.get("fish") or {}

    canonical_hours = record.get("_canonical_hours")
    stage_name = None
    stage_display_label = None
    if canonical_hours is not None:
        stage_name, stage_display_label = get_stage_info(canonical_hours)

    anatomy_names = [
        loc["anatomy_name"]
        for loc in (record.get("anatomical_locations") or [])
        if loc.get("anatomy_name")
    ]

    human_orthologs = [
        HumanOrtholog(
            human_symbol=o.get("human_symbol"),
            human_name=o.get("human_name"),
            omim_id=str(o["omim_id"]) if o.get("omim_id") is not None else None,
            hgnc_id=str(o["hgnc_id"]) if o.get("hgnc_id") is not None else None,
            entrez_gene_id=str(o["entrez_gene_id"]) if o.get("entrez_gene_id") is not None else None,
        )
        for o in (record.get("human_orthologs") or [])
    ]

    disease_associations = [
        DiseaseAssociation(
            do_term_name=d.get("do_term_name"),
            do_term_id=d.get("do_term_id"),
            omim_term_name=d.get("omim_term_name"),
            omim_id=str(d["omim_id"]) if d.get("omim_id") is not None else None,
            human_ortholog_symbol=d.get("human_ortholog_symbol"),
        )
        for d in (record.get("disease_associations") or [])
    ]

    uniprot_ids = [u for u in (record.get("uniprot_ids") or []) if u]

    return ImageRecord(
        image_id=image_id,
        image_url=image_url,
        image_url_fallback=image_url_fallback,
        gene_symbol=gene.get("gene_symbol", ""),
        gene_id=gene.get("gene_id"),
        stage_name=stage_name,
        stage_begin_hours=canonical_hours,
        stage_display_label=stage_display_label,
        anatomy_names=anatomy_names,
        image_preparation=image_info.get("image_preparation"),
        figure_id=image_info.get("figure_id"),
        fish_name=(fish.get("fish_name") or fish.get("fish_abbreviation")),
        human_orthologs=human_orthologs,
        disease_associations=disease_associations,
        uniprot_ids=uniprot_ids,
        publication_id=pub_id or None,
        pubmed_id=str(pub["pubmed_id"]) if pub.get("pubmed_id") is not None else None,
        est_symbol=expression.get("est_symbol"),
        probe_quality=expression.get("probe_quality"),
    )


def _record_matches_anatomy(r: dict, anatomy_lower: str) -> bool:
    """True if any anatomy term on this image contains the search substring."""
    return any(
        anatomy_lower in (loc.get("anatomy_name", "").lower())
        for loc in (r.get("anatomical_locations") or [])
    )


def _filter_records(
    records: list[dict],
    stage_min: float | None,
    stage_max: float | None,
    anatomy: str | None,
) -> list[dict]:
    """Apply stage range and anatomy filters.

    Anatomy is a per-gene gate (marker-discovery semantics): if any image in
    `records` carries the term, ALL the gene's images pass the anatomy check
    and the stage filter then trims by canonical_hours. This lets a user
    spot whether an anatomy-restricted marker also shows up at other stages.
    Caller is responsible for grouping records by gene before passing them in.
    """
    anatomy_lower = anatomy.lower() if anatomy else None
    if anatomy_lower and not any(
        _record_matches_anatomy(r, anatomy_lower) for r in records
    ):
        return []

    result = []
    for r in records:
        ch = r.get("_canonical_hours")
        if ch is None:
            continue
        if stage_min is not None and ch < stage_min:
            continue
        if stage_max is not None and ch > stage_max:
            continue
        result.append(r)
    return result


def _select_representatives(records: list[dict], n: int = 1) -> list[dict]:
    """Group records by canonical stage and pick up to n ranked images per stage."""
    by_stage: dict[float, list[dict]] = defaultdict(list)
    for r in records:
        ch = r.get("_canonical_hours")
        if ch is not None:
            by_stage[ch].append(r)
    result = []
    for hours in sorted(by_stage.keys()):
        result.extend(select_top_n(by_stage[hours], n))
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/genes/search")
def search_genes(request: Request, q: str = Query(default="")) -> list[str]:
    gene_list: list[str] = request.app.state.data["gene_list"]
    if not q:
        return []
    q_lower = q.lower()
    matches = [g for g in gene_list if g.lower().startswith(q_lower)]
    return matches[:20]


@router.get("/genes/{symbol}/images", response_model=list[ImageRecord])
def get_gene_images(
    symbol: str,
    request: Request,
    stage_min: float | None = Query(default=None),
    stage_max: float | None = Query(default=None),
    anatomy: str | None = Query(default=None),
) -> list[ImageRecord]:
    gene_index: dict[str, list[dict]] = request.app.state.data["gene_index"]
    records = gene_index.get(symbol) or gene_index.get(symbol.lower()) or []

    # Try case-insensitive lookup if exact match fails
    if not records:
        symbol_lower = symbol.lower()
        for key, val in gene_index.items():
            if key.lower() == symbol_lower:
                records = val
                break

    filtered = _filter_records(records, stage_min, stage_max, anatomy)
    representatives = _select_representatives(filtered)
    return [_record_to_model(r) for r in representatives]


@router.post("/genes/batch")
def batch_gene_images(body: BatchRequest, request: Request) -> dict[str, list[ImageRecord]]:
    gene_index: dict[str, list[dict]] = request.app.state.data["gene_index"]
    result: dict[str, list[ImageRecord]] = {}

    for symbol in body.genes:
        records = gene_index.get(symbol) or []
        if not records:
            # Case-insensitive fallback
            symbol_lower = symbol.lower()
            for key, val in gene_index.items():
                if key.lower() == symbol_lower:
                    records = val
                    break

        filtered = _filter_records(records, body.stage_min, body.stage_max, body.anatomy)
        representatives = _select_representatives(filtered, body.n_images)
        result[symbol] = [_record_to_model(r) for r in representatives]

    return result


@router.get("/anatomy/search")
def search_anatomy(request: Request, q: str = Query(default="")) -> list[str]:
    anatomy_list: list[str] = request.app.state.data["anatomy_list"]
    if not q:
        return []
    q_lower = q.lower()
    matches = [a for a in anatomy_list if q_lower in a.lower()]
    return matches[:20]


@router.get("/anatomy/{anatomy_name}/genes", response_model=AnatomyGenesResponse)
def get_anatomy_genes(
    anatomy_name: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000),
) -> AnatomyGenesResponse:
    # Exact lowercased lookup (the client passes a verbatim term from the
    # autocomplete dropdown). Note: the image-grid filter in _filter_records
    # uses substring semantics — that asymmetry is intentional.
    idx: dict[str, list[tuple[str, int]]] = request.app.state.data["anatomy_index"]
    pairs = idx.get(anatomy_name.lower())
    if pairs is None:
        raise HTTPException(status_code=404, detail="Anatomy term not found")
    return AnatomyGenesResponse(
        total=len(pairs),
        genes=[AnatomyGene(gene_symbol=s, image_count=c) for s, c in pairs[:limit]],
    )


@router.get("/stages", response_model=list[CanonicalStage])
def get_stages(request: Request) -> list[CanonicalStage]:
    populated: set[float] = request.app.state.data.get("populated_stage_hours") or set()
    return [
        CanonicalStage(stage_name=name, begin_hours=hours, display_label=label)
        for name, hours, label in CANONICAL_STAGES
        if hours in populated
    ]


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
def api_not_found(path: str) -> NoReturn:
    raise HTTPException(status_code=404, detail=f"API endpoint not found: /api/{path}")
