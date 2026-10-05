"""Load and index the Thisse image metadata JSON."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import is_expression_found
from .stage_utils import assign_canonical_stage

# Sidecar written by the extractor next to image_metadata.json: maps each
# canonical ZFIN gene ID to its previous/alias names.
ALIASES_FILE_NAME = "gene_aliases.json"

# Sidecar written by the extractor: the ZFA substructure hierarchy (is_a /
# part of edges) used to match an anatomy term together with its substructures.
ANATOMY_ONTOLOGY_FILE_NAME = "anatomy_ontology.json"


def _find_data_file() -> Path:
    data_dir = os.environ.get("GENE2IMAGE_DATA_DIR")
    if not data_dir:
        raise RuntimeError(
            "GENE2IMAGE_DATA_DIR environment variable is not set. "
            "Point it to the directory containing image_metadata.json."
        )
    base = Path(data_dir)
    # Prefer v2 (corrected per-image stage data) if present
    for name in ("image_metadata_v2.json", "image_metadata.json"):
        path = base / name
        if path.exists():
            return path
    raise FileNotFoundError(
        f"No image_metadata.json or image_metadata_v2.json found in {data_dir}"
    )


def _parse_stage_hours(record: dict) -> None:
    """Parse begin_hours / end_hours strings to float in-place."""
    for stage in record.get("developmental_stages") or []:
        for key in ("begin_hours", "end_hours"):
            val = stage.get(key)
            if val is not None:
                try:
                    stage[key] = float(val)
                except (ValueError, TypeError):
                    stage[key] = None


def load_data() -> dict:
    """Load JSON, clean NaN, parse hours, build indexes. Returns app state dict."""
    path = _find_data_file()

    print(f"Loading data from {path} ...")
    raw = path.read_text(encoding="utf-8")

    # Replace bare NaN (from pandas export) with null before parsing
    raw = re.sub(r"\bNaN\b", "null", raw)

    records: list[dict] = json.loads(raw)
    print(f"Loaded {len(records)} records.")

    gene_index: dict[str, list[dict]] = {}
    anatomy_set: set[str] = set()
    populated_stage_hours: set[float] = set()
    # term (lowercased) -> gene symbol -> image count, for exact-term matching
    # and for matching a term together with its substructures.
    anatomy_counts: dict[str, dict[str, int]] = {}
    anatomy_counts_substructures: dict[str, dict[str, int]] = {}
    ancestors_of = _load_anatomy_ancestors(path.parent)

    for record in records:
        gene = record.get("gene") or {}
        symbol = gene.get("gene_symbol", "")

        # Skip withdrawn genes
        if symbol.startswith("WITHDRAWN"):
            continue

        _parse_stage_hours(record)

        # Pre-compute the canonical stage for this image (single value per image
        # once the extractor correctly assigns per-image stage data).
        ch = assign_canonical_stage(record)
        record["_canonical_hours"] = ch
        if ch is not None:
            populated_stage_hours.add(ch)

        if symbol not in gene_index:
            gene_index[symbol] = []
        gene_index[symbol].append(record)

        # Only positive annotations make an image match an anatomy term. The
        # sets are cached on the record so route handlers never re-derive them.
        direct: set[str] = set()
        with_substructures: set[str] = set()
        for loc in record.get("anatomical_locations") or []:
            name = loc.get("anatomy_name")
            if not name or not is_expression_found(loc):
                continue
            anatomy_set.add(name)
            direct.add(name.lower())
            with_substructures.add(name.lower())
            # Positive substructure evidence deliberately wins over an explicit
            # negative on an ancestor: an image annotated "rhombomere 1" (found)
            # and "brain" (not found) still matches a "brain" substructure
            # search. ZFIN negatives are coarse (mostly "whole organism" on
            # no-signal images) and must not veto finer-grained positives.
            with_substructures.update(ancestors_of(loc.get("anatomy_id")))
        record["_anatomy_direct"] = frozenset(direct)
        record["_anatomy_substructures"] = frozenset(with_substructures)
        for counts, terms in (
            (anatomy_counts, direct),
            (anatomy_counts_substructures, with_substructures),
        ):
            for key in terms:
                per_gene = counts.setdefault(key, {})
                per_gene[symbol] = per_gene.get(symbol, 0) + 1

    gene_list = sorted(gene_index.keys(), key=str.lower)
    anatomy_list = sorted(anatomy_set, key=str.lower)

    # Lowercase → canonical symbol map for O(1) case-insensitive lookup, so
    # _resolve_symbol never has to linearly scan every gene per request (GEN-4).
    # setdefault keeps the first-inserted symbol on the (near-impossible) case
    # collision, matching the previous linear scan's first-match behavior.
    symbol_lower_index: dict[str, str] = {}
    for symbol in gene_index:
        symbol_lower_index.setdefault(symbol.lower(), symbol)

    # Map each stable gene ID present in the dataset to its canonical symbol,
    # then fold the alias sidecar in through that ID so older names resolve to
    # the symbol the rest of the app keys on.
    gene_id_to_symbol: dict[str, str] = {}
    for symbol, recs in gene_index.items():
        for r in recs:
            gid = (r.get("gene") or {}).get("gene_id")
            if gid:
                gene_id_to_symbol.setdefault(gid, symbol)
    alias_index = _build_alias_index(path.parent, gene_id_to_symbol)
    # Sort the alias keys once here, not per search request.
    alias_keys = sorted(alias_index)
    print(f"Indexed {sum(len(v) for v in alias_index.values())} alias → gene matches.")

    # Pre-sort each anatomy's gene list alphabetically by symbol.
    def _sorted_index(counts: dict[str, dict[str, int]]) -> dict[str, list[tuple[str, int]]]:
        return {
            k: sorted(v.items(), key=lambda x: x[0].lower()) for k, v in counts.items()
        }

    anatomy_index = _sorted_index(anatomy_counts)
    anatomy_index_substructures = _sorted_index(anatomy_counts_substructures)

    print(f"Indexed {len(gene_list)} genes, {len(anatomy_list)} anatomy terms.")

    return {
        "gene_index": gene_index,
        "symbol_lower_index": symbol_lower_index,
        "gene_list": gene_list,
        "anatomy_list": anatomy_list,
        "populated_stage_hours": populated_stage_hours,
        "anatomy_index": anatomy_index,
        "anatomy_index_substructures": anatomy_index_substructures,
        "alias_index": alias_index,
        "alias_keys": alias_keys,
    }


def _load_anatomy_ancestors(data_dir: Path):
    """Return a memoized ``anatomy_id -> frozenset(lowercased ancestor names)``.

    Ancestors follow the sidecar's is_a / part of edges transitively (cycles in a
    malformed ontology are tolerated). A missing or
    malformed sidecar yields a function that returns no ancestors, so anatomy
    search degrades to exact-term matching instead of failing startup.
    """
    parents: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    ontology_path = data_dir / ANATOMY_ONTOLOGY_FILE_NAME
    if ontology_path.exists():
        raw = None
        try:
            raw = json.loads(ontology_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as err:
            print(f"Warning: could not read {ontology_path}: {err}")
        # Accept the sidecar only as a whole: both sections present and
        # well-typed. A partially usable file (e.g. parents without names)
        # would silently produce incomplete substructure results, which is
        # worse than the documented exact-match fallback.
        if (
            isinstance(raw, dict)
            and isinstance(raw.get("parents"), dict)
            and isinstance(raw.get("names"), dict)
        ):
            parents = {
                k: [p for p in v if isinstance(p, str)]
                for k, v in raw["parents"].items()
                if isinstance(v, list)
            }
            names = {k: v for k, v in raw["names"].items() if isinstance(v, str)}
        elif raw is not None:
            print(
                f"Warning: {ontology_path.name} is not a valid anatomy ontology "
                "sidecar; anatomy search is exact-term only."
            )
    else:
        print(f"Note: {ontology_path.name} not found; anatomy search is exact-term only.")

    cache: dict[str, frozenset[str]] = {}

    def ancestors_of(term_id: str | None) -> frozenset[str]:
        if not term_id:
            return frozenset()
        if term_id not in cache:
            # Iterative walk up the hierarchy; `seen` doubles as the cycle guard.
            seen: set[str] = set()
            stack = [term_id]
            while stack:
                for parent in parents.get(stack.pop(), []):
                    if parent not in seen and parent != term_id:
                        seen.add(parent)
                        stack.append(parent)
            cache[term_id] = frozenset(names[a].lower() for a in seen if a in names)
        return cache[term_id]

    return ancestors_of


def _build_alias_index(
    data_dir: Path, gene_id_to_symbol: dict[str, str]
) -> dict[str, list[tuple[str, str]]]:
    """Build {alias_lower: [(canonical_symbol, display_alias), ...]} from the sidecar.

    The sidecar maps stable gene IDs to previous/alias names; we keep only the
    genes present in the dataset and drop aliases that already equal the
    canonical symbol (those are covered by the normal symbol search). Missing or
    malformed sidecar → empty index (the feature degrades gracefully).
    """
    alias_path = data_dir / ALIASES_FILE_NAME
    if not alias_path.exists():
        return {}

    try:
        raw = json.loads(alias_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as err:
        print(f"Warning: could not read {alias_path}: {err}")
        return {}

    # Fail closed on an unexpected shape: a non-object top level, or a gene whose
    # aliases are not a list of strings, is skipped rather than crashing startup
    # (or silently iterating the characters of a string).
    if not isinstance(raw, dict):
        print(f"Warning: {alias_path} is not a JSON object; ignoring aliases.")
        return {}

    alias_index: dict[str, list[tuple[str, str]]] = {}
    for gene_id, aliases in raw.items():
        symbol = gene_id_to_symbol.get(gene_id)
        if not symbol or not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str) or not alias:
                continue
            key = alias.lower()
            if key == symbol.lower():
                continue
            bucket = alias_index.setdefault(key, [])
            if all(existing != symbol for existing, _ in bucket):
                bucket.append((symbol, alias))
    return alias_index
