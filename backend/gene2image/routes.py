"""API endpoint definitions."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, build_opener, install_opener
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, Query, Request, Response

from . import s3_images
from .models import (
    AnatomyGene,
    AnatomyGenesResponse,
    AnatomyTerm,
    BatchRequest,
    CanonicalStage,
    DiseaseAssociation,
    GeneFacetsRequest,
    GeneFacetsResponse,
    GeneResolveResult,
    GeneSearchResult,
    HealthResponse,
    HumanOrtholog,
    ImageRecord,
    StageFacet,
)
from .stage_utils import CANONICAL_STAGES, get_stage_info, select_representative, select_top_n

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_image_url(pub_id: str, image_id: str) -> tuple[str, str, str]:
    """Return (annotated_url, plain_url, medium_url) for an image.

    ZFIN hosts a medium-resolution ``_medium.jpg`` (~15KB, 500x374) alongside the
    full-res image (~377KB, 1392x1040) and a tiny ``_thumb.jpg`` (~1KB, 86x64).
    The grid serves the medium variant: a comparison view of N images transfers
    ~N*15 KB instead of ~N*377 KB, yet 500px stays crisp at the grid's ~172px
    display size (even on HiDPI). The thumbnail is too small — 86px upscaled into
    a 172px cell looks blurry (GEN-36). The lightbox still loads full-res.
    """
    # pub_id format: ZDB-PUB-YYMMDD-N  — year is "20" + first 2 chars of third segment
    # e.g. ZDB-PUB-010810-1 → "01" → "2001"
    try:
        year = "20" + pub_id.split("-")[2][:2]
    except (IndexError, AttributeError):
        year = "2000"
    base = f"https://zfin.org/imageLoadUp/{year}/{pub_id}/{image_id}"
    return f"{base}_annot.jpg", f"{base}.jpg", f"{base}_medium.jpg"


def _canonical_zfin_image_url(url: str) -> str:
    """Validate a ZFIN image URL and return it rebuilt from validated parts.

    Returning a URL reconstructed from the checked components (rather than the
    caller reusing its own tainted string) puts the sanitizer on the data path —
    CodeQL's py/full-ssrf treats validate-by-exception as no barrier — and drops
    any query string or fragment that would otherwise ride along to ZFIN.
    """
    try:
        parsed = urlparse(url)
    except ValueError as err:  # e.g. 'Invalid IPv6 URL' from a malformed authority
        raise HTTPException(
            status_code=400, detail="Only zfin.org image URLs are supported"
        ) from err
    if parsed.scheme != "https" or parsed.netloc != "zfin.org":
        raise HTTPException(status_code=400, detail="Only zfin.org image URLs are supported")
    if not parsed.path.startswith("/imageLoadUp/"):
        raise HTTPException(status_code=400, detail="Only ZFIN imageLoadUp URLs are supported")
    return urlunparse(("https", "zfin.org", parsed.path, "", "", ""))


class _NoRedirectHandler(HTTPRedirectHandler):
    """SSRF guard: never follow redirects when fetching ZFIN images.

    ``_canonical_zfin_image_url`` only checks the *initial* URL. urllib follows
    3xx redirects by default and does not re-validate the target, so a redirect
    (e.g. via an open redirect on zfin.org) could point the fetch at an internal
    host such as the cloud metadata endpoint. Returning ``None`` turns any
    redirect into an ``HTTPError`` instead of silently following it.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# urlopen() reads urllib's process-global opener; install one that refuses
# redirects so the image proxy can never be pivoted to an internal host.
install_opener(build_opener(_NoRedirectHandler))


# ZFIN's image host fails intermittently (connection resets, timeouts,
# sporadic 5xx) even when it is otherwise up, which showed as randomly missing
# images in the grid (GEN-46). Those blips are short-lived, so a couple of
# quick same-request retries turn most of them into a served image. 4xx
# responses are definitive (e.g. a genuinely missing _annot.jpg variant) and
# are never retried, so the caller's plain-variant fallback still gets a
# single fast 404.
_ZFIN_FETCH_ATTEMPTS = 3
_ZFIN_FETCH_RETRY_DELAY_SECONDS = 0.3


def _fetch_zfin_image(url: str) -> tuple[bytes, str]:
    url = _canonical_zfin_image_url(url)
    request = UrlRequest(url, headers={"User-Agent": "gene2fish image export"})
    last_err: Exception | None = None
    for attempt in range(_ZFIN_FETCH_ATTEMPTS):
        if attempt:
            # Sync route → FastAPI runs this in a worker thread, so a short
            # blocking sleep between attempts doesn't stall the event loop.
            time.sleep(_ZFIN_FETCH_RETRY_DELAY_SECONDS)
        try:
            with urlopen(request, timeout=15) as resp:
                media_type = resp.headers.get_content_type() or "image/jpeg"
                if not media_type.startswith("image/"):
                    # The proxy only serves images. Refuse anything else so a
                    # non-image (e.g. text/html) upstream response can't be rendered
                    # as a document on our own origin (stored/reflected XSS).
                    raise HTTPException(
                        status_code=502, detail="ZFIN returned non-image content"
                    )
                return resp.read(), media_type
        except HTTPError as err:
            if err.code < 500:
                if err.code == 404:
                    # Load-bearing: image_proxy's _annot.jpg -> plain .jpg
                    # fallback keys on this exact status.
                    raise HTTPException(
                        status_code=404, detail="ZFIN image not found"
                    ) from err
                # Any other non-5xx upstream status (redirect refused by
                # _NoRedirectHandler, 401/403/429) is a gateway condition for
                # our caller, not a status our own resource can carry.
                raise HTTPException(
                    status_code=502,
                    detail=f"ZFIN rejected the image request (upstream {err.code})",
                ) from err
            last_err = err
        except (URLError, TimeoutError) as err:
            last_err = err
    if isinstance(last_err, HTTPError):
        # Exhausted retries on a persistent 5xx — an upstream outage, not a
        # missing image, so the detail must not read like a 404.
        raise HTTPException(
            status_code=last_err.code,
            detail="ZFIN image temporarily unavailable (upstream error)",
        ) from last_err
    raise HTTPException(
        status_code=502, detail="Unable to fetch ZFIN image"
    ) from last_err


def _plain_image_variant(url: str) -> str | None:
    """The un-annotated ``.jpg`` for an ``_annot.jpg`` URL, else ``None``.

    ZFIN hosts annotated (``_annot.jpg``) variants for only some images; for the
    rest the annotated URL 404s while the plain ``.jpg`` exists. Deriving the
    plain URL lets the proxy retry server-side so the browser gets a single 200
    instead of a 404 (plus a client-side refetch) for every such image.
    """
    suffix = "_annot.jpg"
    if url.endswith(suffix):
        return url[: -len(suffix)] + ".jpg"
    return None


def _resolve_image(url: str) -> tuple[bytes, str]:
    """Fetch an image from the S3 mirror if present, else live from ZFIN.

    The S3 path is safe without a separate validation here: s3_images only
    resolves a key for canonical zfin.org/imageLoadUp URLs, and the ZFIN
    fallback validates the URL itself (in _fetch_zfin_image).
    """
    result = s3_images.fetch_image(url) if s3_images.s3_enabled() else None
    if result is not None:
        return result
    return _fetch_zfin_image(url)


def _record_to_model(record: dict) -> ImageRecord:
    """Convert a raw data record to an ImageRecord pydantic model."""
    image_id = record.get("image_id", "")
    pub = record.get("publication") or {}
    pub_id = pub.get("publication_id") or ""
    image_url, image_url_fallback, image_medium_url = _build_image_url(pub_id, image_id)

    gene = record.get("gene") or {}
    image_info = record.get("image_info") or {}
    expression = record.get("expression") or {}
    fish = record.get("fish") or {}

    canonical_hours = record.get("_canonical_hours")
    stage_name = None
    stage_display_label = None
    if canonical_hours is not None:
        stage_name, stage_display_label = get_stage_info(canonical_hours)

    anatomy_terms = [
        AnatomyTerm(
            anatomy_name=loc["anatomy_name"],
            anatomy_id=loc.get("anatomy_id"),
        )
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
        image_medium_url=image_medium_url,
        gene_symbol=gene.get("gene_symbol", ""),
        gene_id=gene.get("gene_id"),
        gene_name=gene.get("gene_name"),
        stage_name=stage_name,
        stage_begin_hours=canonical_hours,
        stage_display_label=stage_display_label,
        anatomy_terms=anatomy_terms,
        image_preparation=image_info.get("image_preparation"),
        figure_id=image_info.get("figure_id"),
        fish_name=(fish.get("fish_name") or fish.get("fish_abbreviation")),
        human_orthologs=human_orthologs,
        disease_associations=disease_associations,
        uniprot_ids=uniprot_ids,
        publication_id=pub_id or None,
        pubmed_id=str(pub["pubmed_id"]) if pub.get("pubmed_id") is not None else None,
        est_id=expression.get("est_id"),
        est_symbol=expression.get("est_symbol"),
        probe_quality=expression.get("probe_quality"),
    )


def _record_matches_anatomy(r: dict, anatomy_lower: str) -> bool:
    """True if any anatomy term on this image contains the search substring."""
    return any(
        anatomy_lower in (loc.get("anatomy_name", "").lower())
        for loc in (r.get("anatomical_locations") or [])
    )


def _record_matches_exact_anatomy(r: dict, anatomy_terms_lower: set[str]) -> bool:
    """True if any anatomy term on this image exactly matches a selected term."""
    return any(
        loc.get("anatomy_name", "").lower() in anatomy_terms_lower
        for loc in (r.get("anatomical_locations") or [])
    )


def _get_anatomy_gene_pairs(
    anatomy_terms: list[str],
    request: Request,
) -> list[tuple[str, int]] | None:
    """Return alphabetized genes that are present in every selected anatomy term."""
    terms = []
    seen = set()
    for term in anatomy_terms:
        key = term.strip().lower()
        if key and key not in seen:
            terms.append(key)
            seen.add(key)

    if not terms:
        return []

    idx: dict[str, list[tuple[str, int]]] = request.app.state.data["anatomy_index"]
    per_term_symbols = []
    for term in terms:
        pairs = idx.get(term)
        if pairs is None:
            return None
        per_term_symbols.append({symbol for symbol, _ in pairs})

    matched_symbols = set.intersection(*per_term_symbols)
    terms_set = set(terms)
    gene_index: dict[str, list[dict]] = request.app.state.data["gene_index"]
    pairs = []
    for symbol in matched_symbols:
        records = gene_index.get(symbol) or []
        image_count = sum(
            1 for record in records if _record_matches_exact_anatomy(record, terms_set)
        )
        pairs.append((symbol, image_count))

    return sorted(pairs, key=lambda x: x[0].lower())


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


def _resolve_symbol(symbol: str, data: dict) -> tuple[str, str | None] | None:
    """Resolve a user-supplied gene symbol to the canonical symbol in the dataset.

    Tries an exact match, then a case-insensitive match (via the precomputed
    lowercase index — O(1), no per-request linear scan; GEN-4), then falls back
    to the alias index so a previous/alias name (e.g. "oct4") resolves to the
    canonical gene (e.g. "pou5f3"). Returns ``(canonical_symbol, matched_alias)``
    where ``matched_alias`` is the previous/alias name that matched (``None`` when
    the gene was found by its current symbol), or ``None`` when the symbol does
    not correspond to any gene in the dataset.
    """
    gene_index: dict[str, list[dict]] = data["gene_index"]
    if symbol in gene_index:
        return symbol, None

    symbol_lower = symbol.lower()
    symbol_lower_index: dict[str, str] = data.get("symbol_lower_index") or {}
    canonical = symbol_lower_index.get(symbol_lower)
    if canonical is not None:
        return canonical, None

    alias_index: dict[str, list[tuple[str, str]]] = data.get("alias_index") or {}
    for canonical, display_alias in alias_index.get(symbol_lower, []):
        if canonical in gene_index:
            return canonical, display_alias

    return None


def _records_for_symbol(symbol: str, data: dict) -> list[dict]:
    """Resolve a gene symbol to its image records (empty list when unknown)."""
    resolved = _resolve_symbol(symbol, data)
    if resolved is None:
        return []
    return data["gene_index"].get(resolved[0], [])


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

@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/genes/search", response_model=list[GeneSearchResult])
def search_genes(request: Request, q: str = Query(default="")) -> list[GeneSearchResult]:
    if not q:
        return []
    data = request.app.state.data
    gene_list: list[str] = data["gene_list"]
    alias_index: dict[str, list[tuple[str, str]]] = data.get("alias_index") or {}
    # Alias keys are sorted once at load time (see load_data), not per request.
    alias_keys: list[str] = data.get("alias_keys") or []
    q_lower = q.lower()
    limit = 20

    results: list[GeneSearchResult] = []
    seen: set[str] = set()

    # Current symbols first (prefix match) — these are the primary results.
    for g in gene_list:
        if g.lower().startswith(q_lower):
            results.append(GeneSearchResult(symbol=g))
            seen.add(g)
            if len(results) >= limit:
                return results

    # Then previous/alias names, resolved to their canonical symbol. Iterated in
    # the precomputed sorted order for determinism; a canonical symbol already
    # surfaced above is not repeated.
    for alias in alias_keys:
        if not alias.startswith(q_lower):
            continue
        for symbol, display_alias in alias_index[alias]:
            if symbol in seen:
                continue
            results.append(GeneSearchResult(symbol=symbol, matched_alias=display_alias))
            seen.add(symbol)
            if len(results) >= limit:
                return results

    return results


@router.get("/genes/{symbol}/resolve", response_model=GeneResolveResult)
def resolve_gene(symbol: str, request: Request) -> GeneResolveResult:
    """Resolve a typed gene name to its canonical symbol, or 404 if unknown.

    The client calls this before opening a comparison column so an invalid or
    nonsensical name is rejected up front instead of silently creating an empty
    column (the batch endpoint returns no records for unknown symbols).
    """
    resolved = _resolve_symbol(symbol, request.app.state.data)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"No gene matching '{symbol}'")
    canonical, matched_alias = resolved
    return GeneResolveResult(symbol=canonical, matched_alias=matched_alias)


@router.get("/image-proxy")
def image_proxy(url: str = Query(...)) -> Response:
    # Rebuild the URL from validated parts before S3 keying and annot-fallback
    # so a query string or fragment cannot skip `_plain_image_variant`.
    # `_fetch_zfin_image` still sanitizes immediately before UrlRequest (CodeQL).
    url = _canonical_zfin_image_url(url)
    # Serve the image from our own mirror first (S3) so a temporary ZFIN outage
    # doesn't break image loading; fall back to fetching live from ZFIN when the
    # object isn't mirrored or no bucket is configured (GEN-22).
    try:
        data, media_type = _resolve_image(url)
    except HTTPException as err:
        # ZFIN has no annotated (`_annot.jpg`) variant for many images and 404s
        # on them; retry the plain `.jpg` server-side so the browser gets a
        # single 200 instead of a 404 (plus a client-side refetch) per image.
        plain = _plain_image_variant(url)
        if err.status_code == 404 and plain is not None:
            data, media_type = _resolve_image(plain)
        else:
            raise
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
            # Belt-and-suspenders with the image/* check in _fetch_zfin_image:
            # never let a browser MIME-sniff a proxied response into HTML.
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/genes/{symbol}/images", response_model=list[ImageRecord])
def get_gene_images(
    symbol: str,
    request: Request,
    stage_min: float | None = Query(default=None),
    stage_max: float | None = Query(default=None),
    anatomy: str | None = Query(default=None),
) -> list[ImageRecord]:
    records = _records_for_symbol(symbol, request.app.state.data)
    filtered = _filter_records(records, stage_min, stage_max, anatomy)
    representatives = _select_representatives(filtered)
    return [_record_to_model(r) for r in representatives]


@router.post("/genes/batch")
def batch_gene_images(body: BatchRequest, request: Request) -> dict[str, list[ImageRecord]]:
    result: dict[str, list[ImageRecord]] = {}

    for symbol in body.genes:
        records = _records_for_symbol(symbol, request.app.state.data)
        filtered = _filter_records(records, body.stage_min, body.stage_max, body.anatomy)
        representatives = _select_representatives(filtered, body.n_images)
        result[symbol] = [_record_to_model(r) for r in representatives]

    return result


@router.post("/genes/facets", response_model=GeneFacetsResponse)
def gene_facets(body: GeneFacetsRequest, request: Request) -> GeneFacetsResponse:
    """Report which stage/anatomy filter options have images for the given genes.

    Powers the context-aware filters (GEN-23): the client greys out options that
    would return nothing for the genes currently in the comparison. Union
    semantics — an option is reported if it matches ANY gene in the set — because
    the grid renders each gene in its own column, so an option that yields images
    for even one gene still produces useful results. Unknown symbols are ignored
    and duplicate/alias references to the same gene are counted once.
    """
    data = request.app.state.data
    gene_index: dict[str, list[dict]] = data["gene_index"]

    stage_counts: dict[float, int] = defaultdict(int)
    anatomy_counts: dict[str, int] = defaultdict(int)
    seen: set[str] = set()

    for symbol in body.genes:
        resolved = _resolve_symbol(symbol, data)
        if resolved is None:
            continue
        canonical = resolved[0]
        if canonical in seen:
            continue
        seen.add(canonical)
        for record in gene_index.get(canonical, []):
            ch = record.get("_canonical_hours")
            if ch is not None:
                stage_counts[ch] += 1
            for loc in record.get("anatomical_locations") or []:
                name = loc.get("anatomy_name")
                if name:
                    anatomy_counts[name.lower()] += 1

    stages = [
        StageFacet(begin_hours=hours, image_count=count)
        for hours, count in sorted(stage_counts.items())
    ]
    return GeneFacetsResponse(stages=stages, anatomy=dict(anatomy_counts))


@router.get("/anatomy/search")
def search_anatomy(
    request: Request,
    q: str = Query(default=""),
    limit: int = Query(default=250, ge=1, le=500),
) -> list[str]:
    anatomy_list: list[str] = request.app.state.data["anatomy_list"]
    if not q:
        return anatomy_list[:limit]
    q_lower = q.lower()
    matches = [a for a in anatomy_list if q_lower in a.lower()]
    return matches[:limit]


@router.get("/anatomy/genes", response_model=AnatomyGenesResponse)
def get_anatomy_genes_for_terms(
    request: Request,
    anatomy: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
) -> AnatomyGenesResponse:
    pairs = _get_anatomy_gene_pairs(anatomy or [], request)
    if pairs is None:
        raise HTTPException(status_code=404, detail="Anatomy term not found")
    return AnatomyGenesResponse(
        total=len(pairs),
        genes=[AnatomyGene(gene_symbol=s, image_count=c) for s, c in pairs[:limit]],
    )


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
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    response_model=None,
)
def api_not_found(path: str) -> NoReturn:
    raise HTTPException(status_code=404, detail=f"API endpoint not found: /api/{path}")
