"""Pydantic response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HumanOrtholog(BaseModel):
    human_symbol: str | None = None
    human_name: str | None = None
    omim_id: str | None = None
    hgnc_id: str | None = None
    entrez_gene_id: str | None = None


class AnatomyTerm(BaseModel):
    anatomy_name: str
    # ZFA ontology identifier, e.g. "ZFA:0000615". May be absent for records
    # that only carry a free-text anatomy label.
    anatomy_id: str | None = None


class DiseaseAssociation(BaseModel):
    do_term_name: str | None = None
    do_term_id: str | None = None
    omim_term_name: str | None = None
    omim_id: str | None = None
    human_ortholog_symbol: str | None = None


class ImageRecord(BaseModel):
    image_id: str
    image_url: str
    image_url_fallback: str
    image_thumb_url: str
    gene_symbol: str
    gene_id: str | None = None
    gene_name: str | None = None
    stage_name: str | None = None
    stage_begin_hours: float | None = None
    stage_display_label: str | None = None
    anatomy_terms: list[AnatomyTerm] = []
    image_preparation: str | None = None
    figure_id: str | None = None
    fish_name: str | None = None
    human_orthologs: list[HumanOrtholog] = []
    disease_associations: list[DiseaseAssociation] = []
    uniprot_ids: list[str] = []
    publication_id: str | None = None
    pubmed_id: str | None = None
    est_id: str | None = None
    est_symbol: str | None = None
    probe_quality: str | None = None


class GeneSearchResult(BaseModel):
    symbol: str
    # The previous/alias name that matched the query, when the gene was found
    # via an alias rather than its current symbol (e.g. "oct4" → "pou5f3").
    matched_alias: str | None = None


class GeneResolveResult(BaseModel):
    # The canonical dataset symbol a user-supplied name resolves to. The client
    # validates a typed gene against this before opening a comparison column, so
    # an unknown name 404s instead of creating an empty column.
    symbol: str
    # The previous/alias name that matched, when resolved via an alias rather
    # than the current symbol (e.g. "oct4" → "pou5f3").
    matched_alias: str | None = None


class CanonicalStage(BaseModel):
    stage_name: str
    begin_hours: float
    display_label: str


class BatchRequest(BaseModel):
    # Bound the request so a giant POST is rejected at validation (422) before
    # the handler does any per-gene work — the comparison grid never sends more
    # than a handful of genes, so 200 is generous headroom, and n_images caps
    # how many images per stage are returned (GEN-4).
    genes: list[str] = Field(max_length=200)
    stage_min: float | None = None
    stage_max: float | None = None
    anatomy: str | None = None
    n_images: int = Field(default=1, ge=1, le=10)


class GeneFacetsRequest(BaseModel):
    genes: list[str]


class StageFacet(BaseModel):
    begin_hours: float
    image_count: int


class GeneFacetsResponse(BaseModel):
    # Which filter options have any images for the current gene set (union
    # semantics: an option counts if it matches ANY gene in the comparison).
    # `stages` lists canonical begin_hours with a positive image count; `anatomy`
    # maps a lowercased anatomy term to its image count across those genes.
    stages: list[StageFacet]
    anatomy: dict[str, int]


class AnatomyGene(BaseModel):
    gene_symbol: str
    image_count: int


class AnatomyGenesResponse(BaseModel):
    total: int
    genes: list[AnatomyGene]


class HealthResponse(BaseModel):
    status: str
