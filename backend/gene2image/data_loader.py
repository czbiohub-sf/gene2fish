"""Load and index the Thisse image metadata JSON."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .stage_utils import assign_canonical_stage

# Sidecar written by the extractor next to image_metadata.json: maps each
# canonical ZFIN gene ID to its previous/alias names.
ALIASES_FILE_NAME = "gene_aliases.json"


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
    anatomy_counts: dict[str, dict[str, int]] = {}

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

        for loc in record.get("anatomical_locations") or []:
            name = loc.get("anatomy_name")
            if name:
                anatomy_set.add(name)
                key = name.lower()
                per_gene = anatomy_counts.get(key)
                if per_gene is None:
                    per_gene = {}
                    anatomy_counts[key] = per_gene
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
    anatomy_index: dict[str, list[tuple[str, int]]] = {
        k: sorted(v.items(), key=lambda x: x[0].lower())
        for k, v in anatomy_counts.items()
    }

    print(f"Indexed {len(gene_list)} genes, {len(anatomy_list)} anatomy terms.")

    return {
        "gene_index": gene_index,
        "symbol_lower_index": symbol_lower_index,
        "gene_list": gene_list,
        "anatomy_list": anatomy_list,
        "populated_stage_hours": populated_stage_hours,
        "anatomy_index": anatomy_index,
        "alias_index": alias_index,
        "alias_keys": alias_keys,
    }


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
