"""Anatomy search accuracy: negative annotations and substructure matching.

ZFIN records some anatomy annotations as expression NOT found; those must never
make a gene match a structure. And like ZFIN's own expression search, selecting
a term (e.g. "brain") should by default also match images annotated to its
substructures (e.g. "hindbrain"), with an opt-out for exact-term matching.
"""

import json
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from zfin_image_metadata_extractor import build_anatomy_ontology  # noqa: E402

BRAIN = "ZFA:0000008"
HINDBRAIN = "ZFA:0000029"
RHOMBOMERE_1 = "ZFA:0001031"
HEART = "ZFA:0000114"

ONTOLOGY = {
    "parents": {HINDBRAIN: [BRAIN], RHOMBOMERE_1: [HINDBRAIN]},
    "names": {
        BRAIN: "brain",
        HINDBRAIN: "hindbrain",
        RHOMBOMERE_1: "rhombomere 1",
        HEART: "heart",
    },
}


def _loc(name, anatomy_id, found="t"):
    return {"anatomy_name": name, "anatomy_id": anatomy_id, "expression_found": found}


def _record(symbol, image_id, locations, hours="16.0"):
    return {
        "image_id": image_id,
        "gene": {"gene_symbol": symbol},
        "anatomical_locations": locations,
        "developmental_stages": [{"begin_hours": hours, "end_hours": hours}],
    }


RECORDS = [
    # braingene: annotated directly to brain.
    _record("braingene", "ZDB-IMAGE-1", [_loc("brain", BRAIN)]),
    # hbgene: annotated to hindbrain only (twice), plus a rhombomere 1 image.
    _record("hbgene", "ZDB-IMAGE-2", [_loc("hindbrain", HINDBRAIN)]),
    _record("hbgene", "ZDB-IMAGE-3", [_loc("rhombomere 1", RHOMBOMERE_1)]),
    # heartgene: expressed in heart, explicitly NOT expressed in brain.
    _record(
        "heartgene",
        "ZDB-IMAGE-4",
        [_loc("heart", HEART), _loc("brain", BRAIN, found="f")],
    ),
    # notfoundonly: its only annotation is a negative one.
    _record("notfoundonly", "ZDB-IMAGE-5", [_loc("somite", "ZFA:0000155", found="f")]),
]


def _client(tmp_path, monkeypatch, records=RECORDS, ontology=ONTOLOGY):
    (tmp_path / "image_metadata.json").write_text(json.dumps(records))
    if ontology is not None:
        text = ontology if isinstance(ontology, str) else json.dumps(ontology)
        (tmp_path / "anatomy_ontology.json").write_text(text)
    monkeypatch.setenv("GENE2IMAGE_DATA_DIR", str(tmp_path))
    from gene2image.main import app

    return TestClient(app)


def _genes(resp):
    assert resp.status_code == 200, resp.text
    return {g["gene_symbol"]: g["image_count"] for g in resp.json()["genes"]}


# --- negative annotations ---------------------------------------------------


def test_not_found_annotation_does_not_match_anatomy(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        brain = _genes(c.get("/api/anatomy/brain/genes", params={"include_substructures": False}))
        heart = _genes(c.get("/api/anatomy/heart/genes"))

    # heartgene's brain annotation is "expression not found": it must not match.
    assert "heartgene" not in brain
    assert heart == {"heartgene": 1}


def test_term_with_only_negative_annotations_is_not_offered(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        terms = c.get("/api/anatomy/search").json()
        resp = c.get("/api/anatomy/somite/genes")

    assert "somite" not in terms
    assert resp.status_code == 404


def test_facets_ignore_not_found_annotations(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        resp = c.post(
            "/api/genes/facets",
            json={"genes": ["heartgene"], "include_substructures": False},
        )

    assert resp.status_code == 200
    assert resp.json()["anatomy"] == {"heart": 1}


def test_lightbox_labels_not_found_terms(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        resp = c.post("/api/genes/batch", json={"genes": ["heartgene"]})

    assert resp.status_code == 200
    terms = resp.json()["heartgene"][0]["anatomy_terms"]
    assert {t["anatomy_name"]: t["expression_found"] for t in terms} == {
        "heart": True,
        "brain": False,
    }


def test_grid_anatomy_gate_ignores_not_found_annotations(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        resp = c.post("/api/genes/batch", json={"genes": ["heartgene"], "anatomy": "brain"})

    assert resp.status_code == 200
    assert resp.json()["heartgene"] == []


# --- substructures ------------------------------------------------------------


def test_anatomy_search_includes_substructures_by_default(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        brain = _genes(c.get("/api/anatomy/brain/genes"))
        hindbrain = _genes(c.get("/api/anatomy/hindbrain/genes"))

    # hindbrain and rhombomere 1 are (transitively) part of brain.
    assert brain == {"braingene": 1, "hbgene": 2}
    assert hindbrain == {"hbgene": 2}


def test_positive_substructure_evidence_wins_over_negative_ancestor(tmp_path, monkeypatch):
    """A positive in a substructure deliberately beats an explicit negative above it.

    ZFIN negatives are coarse (mostly "whole organism" on no-signal images); an
    image annotated "rhombomere 1" (found) and "brain" (not found) must still
    match a "brain" substructure search — the finer-grained positive wins. The
    negative still keeps the image out of exact-term "brain" matching.
    """
    records = RECORDS + [
        _record(
            "mixedgene",
            "ZDB-IMAGE-8",
            [_loc("rhombomere 1", RHOMBOMERE_1), _loc("brain", BRAIN, found="f")],
        )
    ]
    with _client(tmp_path, monkeypatch, records=records) as c:
        brain = _genes(c.get("/api/anatomy/brain/genes"))
        exact = _genes(c.get("/api/anatomy/brain/genes", params={"include_substructures": False}))

    assert brain == {"braingene": 1, "hbgene": 2, "mixedgene": 1}
    assert "mixedgene" not in exact


def test_exact_term_matching_can_be_requested(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        brain = _genes(c.get("/api/anatomy/brain/genes", params={"include_substructures": False}))
        hindbrain = _genes(
            c.get("/api/anatomy/hindbrain/genes", params={"include_substructures": "false"})
        )

    assert brain == {"braingene": 1}
    assert hindbrain == {"hbgene": 1}


def test_multi_term_and_selection_uses_substructures(tmp_path, monkeypatch):
    records = RECORDS + [
        _record("both", "ZDB-IMAGE-6", [_loc("rhombomere 1", RHOMBOMERE_1)]),
        _record("both", "ZDB-IMAGE-7", [_loc("heart", HEART)]),
    ]
    with _client(tmp_path, monkeypatch, records=records) as c:
        default = _genes(c.get("/api/anatomy/genes", params=[("anatomy", "brain"), ("anatomy", "heart")]))
        exact = _genes(
            c.get(
                "/api/anatomy/genes",
                params=[("anatomy", "brain"), ("anatomy", "heart"), ("include_substructures", "false")],
            )
        )

    assert default == {"both": 2}
    assert exact == {}


def test_facets_include_substructures_by_default(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as c:
        default = c.post("/api/genes/facets", json={"genes": ["hbgene"]}).json()["anatomy"]
        exact = c.post(
            "/api/genes/facets", json={"genes": ["hbgene"], "include_substructures": False}
        ).json()["anatomy"]

    assert default == {"brain": 2, "hindbrain": 2, "rhombomere 1": 1}
    assert exact == {"hindbrain": 1, "rhombomere 1": 1}


def test_dropdown_lists_only_directly_annotated_terms(tmp_path, monkeypatch):
    records = [_record("hbgene", "ZDB-IMAGE-2", [_loc("hindbrain", HINDBRAIN)])]
    with _client(tmp_path, monkeypatch, records=records) as c:
        terms = c.get("/api/anatomy/search").json()
        brain = c.get("/api/anatomy/brain/genes")

    # The dropdown keeps the dataset's own vocabulary; ancestors are still
    # searchable when requested explicitly.
    assert terms == ["hindbrain"]
    assert _genes(brain) == {"hbgene": 1}


def test_missing_ontology_falls_back_to_exact_matching(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch, ontology=None) as c:
        brain = _genes(c.get("/api/anatomy/brain/genes"))

    assert brain == {"braingene": 1}


def test_malformed_ontology_falls_back_to_exact_matching(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch, ontology="{not json") as c:
        brain = _genes(c.get("/api/anatomy/brain/genes"))

    assert brain == {"braingene": 1}


def test_wrong_shape_ontology_falls_back_to_exact_matching(tmp_path, monkeypatch):
    # Parseable JSON that is not a valid sidecar (here: missing "names") is
    # rejected as a whole — a partially usable file would silently produce
    # incomplete substructure results instead of the documented fallback.
    for bad in ([1, 2], {"parents": {HINDBRAIN: [BRAIN]}}, {"parents": [], "names": {}}):
        with _client(tmp_path, monkeypatch, ontology=bad) as c:
            brain = _genes(c.get("/api/anatomy/brain/genes"))

        assert brain == {"braingene": 1}


def test_ontology_cycle_does_not_hang(tmp_path, monkeypatch):
    ontology = {
        "parents": {HINDBRAIN: [BRAIN], BRAIN: [HINDBRAIN]},
        "names": ONTOLOGY["names"],
    }
    with _client(tmp_path, monkeypatch, ontology=ontology) as c:
        brain = _genes(c.get("/api/anatomy/brain/genes"))

    assert brain == {"braingene": 1, "hbgene": 1}


# --- extractor sidecar ----------------------------------------------------------


def test_build_anatomy_ontology_keeps_substructure_edges_only():
    relationships = pd.DataFrame(
        [
            {"Parent Item ID": BRAIN, "Child Item ID": HINDBRAIN, "Relationship Type ID": "part of"},
            {"Parent Item ID": "ZFA:0001488", "Child Item ID": HINDBRAIN, "Relationship Type ID": "is_a"},
            {"Parent Item ID": "ZFA:0007043", "Child Item ID": HINDBRAIN, "Relationship Type ID": "develops from"},
            {"Parent Item ID": BRAIN, "Child Item ID": HINDBRAIN, "Relationship Type ID": "part of"},
            {"Parent Item ID": None, "Child Item ID": HEART, "Relationship Type ID": "is_a"},
        ]
    )
    anatomy = pd.DataFrame(
        [
            {"Anatomy ID": BRAIN, "Anatomy Name": "brain"},
            {"Anatomy ID": HINDBRAIN, "Anatomy Name": "hindbrain"},
        ]
    )

    ontology = build_anatomy_ontology(relationships, anatomy)

    assert ontology == {
        "parents": {HINDBRAIN: [BRAIN, "ZFA:0001488"]},
        "names": {BRAIN: "brain", HINDBRAIN: "hindbrain"},
    }


def test_build_anatomy_ontology_tolerates_missing_inputs():
    assert build_anatomy_ontology(None, None) == {"parents": {}, "names": {}}


# --- representative-image ranking ----------------------------------------------


def test_not_found_terms_do_not_boost_image_ranking():
    from gene2image.stage_utils import select_top_n

    def img(image_id, locations):
        return {
            "image_id": image_id,
            "image_info": {"image_preparation": "whole-mount"},
            "anatomical_locations": locations,
        }

    no_signal = img("ZDB-IMAGE-9", [_loc("whole organism", "ZFA:0001094", found="f"),
                                    _loc("unspecified", "ZFA:0001093", found="f")])
    expressed = img("ZDB-IMAGE-1", [_loc("hindbrain", HINDBRAIN)])

    # The image with real expression wins despite having fewer annotations
    # (and a lower image ID, the final tie-breaker).
    assert [i["image_id"] for i in select_top_n([no_signal, expressed], 1)] == ["ZDB-IMAGE-1"]
