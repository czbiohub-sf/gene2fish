#!/usr/bin/env python3
"""
ZFIN Image Metadata Extractor

This script extracts all available metadata linked to ZFIN image IDs by joining
multiple ZFIN data files. It outputs both TSV and JSON formats.

Files are automatically downloaded from ZFIN if not present locally.

Required TSV files (auto-downloaded from https://zfin.org/downloads):
1.  ImageFigures.txt              - Image to Figure mapping
2.  xpatfig_fish.txt              - Figure to Expression ID mapping  
3.  xpat_fish.txt                 - Expression details (gene, publication, fish, environment)
4.  xpat_stage_anatomy.txt        - Stage and anatomy for expression results
5.  stage_ontology.txt            - Stage ID to name/hours mapping
6.  anatomy_item.txt              - Anatomy ID to name mapping
7.  gene.txt                      - Gene details (NCBI ID, SO ID)
8.  wildtypes_fish.txt            - Fish/strain details
9.  xpat_environment_fish.txt     - Environment/condition details
10. pub_to_pubmed_id_translation.txt - Publication to PubMed ID mapping
11. human_orthos.txt              - Human ortholog information
12. gene2DiseaseViaOrthology.txt  - Disease associations via orthologs
13. uniprot.txt                   - UniProt protein IDs

Usage:
    # Process all images (auto-downloads files to ./zfin_data):
    python zfin_image_metadata_extractor.py

    # Process specific image IDs:
    python zfin_image_metadata_extractor.py --image-ids ZDB-IMAGE-021202-285,ZDB-IMAGE-011001-1

    # Specify custom directories:
    python zfin_image_metadata_extractor.py --input-dir /path/to/files --output-prefix my_output

    # Skip auto-download (fail if files missing):
    python zfin_image_metadata_extractor.py --no-download
"""

import pandas as pd
import json
import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# Define the required files and their download URLs
REQUIRED_FILES = {
    "ImageFigures.txt": "https://zfin.org/downloads/file/ImageFigures.txt",
    "xpatfig_fish.txt": "https://zfin.org/downloads/file/xpatfig_fish.txt",
    "xpat_fish.txt": "https://zfin.org/downloads/file/xpat_fish.txt",
    "xpat_stage_anatomy.txt": "https://zfin.org/downloads/file/xpat_stage_anatomy.txt",
    "stage_ontology.txt": "https://zfin.org/downloads/file/stage_ontology.txt",
    "anatomy_item.txt": "https://zfin.org/downloads/file/anatomy_item.txt",
    "gene.txt": "https://zfin.org/downloads/file/gene.txt",
    "wildtypes_fish.txt": "https://zfin.org/downloads/file/wildtypes_fish.txt",
    "xpat_environment_fish.txt": "https://zfin.org/downloads/file/xpat_environment_fish.txt",
    "pub_to_pubmed_id_translation.txt": "https://zfin.org/downloads/file/pub_to_pubmed_id_translation.txt",
    "human_orthos.txt": "https://zfin.org/downloads/file/human_orthos.txt",
    "gene2DiseaseViaOrthology.txt": "https://zfin.org/downloads/file/gene2DiseaseViaOrthology.txt",
    "uniprot.txt": "https://zfin.org/downloads/file/uniprot.txt",
}

# Column name mappings for each file
COLUMN_NAMES = {
    "ImageFigures.txt": ["Image ID", "Figure ID", "Image Preparation"],
    "xpatfig_fish.txt": ["Expression ID", "Expression Result ID", "Figure ID"],
    "xpat_fish.txt": [
        "Gene ID", "Gene Symbol", "EST ID", "EST Symbol", "Expression Type",
        "Expression Type MMO ID", "Expression ID", "Publication ID", "Fish ID",
        "Environment ID", "Probe Quality"
    ],
    "xpat_stage_anatomy.txt": [
        "Expression Result ID", "Expression ID", "Start Stage ID", "End Stage ID",
        "Anatomy Super Term ID", "Anatomy Sub Term ID", "Expression Found"
    ],
    "stage_ontology.txt": ["Stage ID", "Stage OBO ID", "Stage Name", "Begin Hours", "End Hours"],
    "anatomy_item.txt": ["Anatomy ID", "Anatomy Name", "Start Stage ID", "End Stage ID"],
    "gene.txt": ["ZFIN ID", "SO ID", "Symbol", "NCBI Gene ID"],
    "wildtypes_fish.txt": ["Fish ID", "Fish Name", "Fish Abbreviation", "Genotype ID"],
    "xpat_environment_fish.txt": [
        "Environment ID", "ZECO Term Name", "ZECO Term ID", "Chebi Term Name",
        "Chebi Term ID", "ZFA Term Name", "ZFA Term ID", "Affected Structure Subterm Name",
        "Affected Structure Subterm ID", "NCBI Taxon Name", "NCBI Taxon ID"
    ],
    "pub_to_pubmed_id_translation.txt": ["Publication ZFIN ID", "PubMed ID"],
    "human_orthos.txt": [
        "ZFIN ID", "ZFIN Symbol", "ZFIN Name", "Human Symbol", "Human Name",
        "OMIM ID", "Gene ID", "HGNC ID", "Evidence", "Pub ID", "ZFIN Abbreviation Name",
        "ECO ID", "ECO Term Name"
    ],
    "gene2DiseaseViaOrthology.txt": [
        "Zebrafish Gene ID", "Zebrafish Gene Symbol", "Human Ortholog Entrez Gene Id",
        "Human Ortholog Symbol", "DO Term Name", "DO Term ID", "OMIM Term Name",
        "OMIM ID", "Evidence Code", "Publication"
    ],
    "uniprot.txt": ["ZFIN ID", "SO ID", "Symbol", "UniProt ID"],
}


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def download_file(url: str, output_path: Path, max_retries: int = 3) -> bool:
    """
    Download a file from URL with progress indicator and retry logic.
    Returns True if successful, False otherwise.
    """
    for attempt in range(max_retries):
        try:
            # Create request with User-Agent header
            request = Request(url, headers={'User-Agent': 'ZFIN-Metadata-Extractor/1.0'})

            with urlopen(request, timeout=60) as response:
                # Get file size if available
                total_size = response.headers.get('Content-Length')
                total_size = int(total_size) if total_size else None

                # Download with progress
                downloaded = 0
                chunk_size = 8192

                with open(output_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Show progress
                        if total_size:
                            percent = (downloaded / total_size) * 100
                            sys.stdout.write(f"\r    Progress: {percent:.1f}% ({format_size(downloaded)}/{format_size(total_size)})")
                        else:
                            sys.stdout.write(f"\r    Downloaded: {format_size(downloaded)}")
                        sys.stdout.flush()

                print()  # New line after progress
                return True

        except (URLError, HTTPError, TimeoutError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"\n    Attempt {attempt + 1} failed: {e}")
                print(f"    Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"\n    Failed after {max_retries} attempts: {e}")
                if output_path.exists():
                    output_path.unlink()  # Remove partial download
                return False
        except Exception as e:
            print(f"\n    Unexpected error: {e}")
            if output_path.exists():
                output_path.unlink()
            return False

    return False


def ensure_files_available(input_dir: Path, auto_download: bool = True) -> List[str]:
    """
    Check for required files and download missing ones if auto_download is True.
    Returns list of missing files that couldn't be obtained.
    """
    input_dir.mkdir(parents=True, exist_ok=True)

    missing_files = []
    files_to_download = []

    # Check which files exist
    print("\nChecking for required ZFIN data files...")
    for filename in REQUIRED_FILES:
        filepath = input_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  ✓ {filename} ({format_size(size)})")
        else:
            print(f"  ✗ {filename} - not found")
            files_to_download.append(filename)

    # Download missing files
    if files_to_download:
        if not auto_download:
            print(f"\n❌ Missing {len(files_to_download)} required files.")
            print("Run without --no-download flag to auto-download, or download manually from:")
            for f in files_to_download:
                print(f"  {REQUIRED_FILES[f]}")
            return files_to_download

        print(f"\n📥 Downloading {len(files_to_download)} missing files...")

        for i, filename in enumerate(files_to_download, 1):
            url = REQUIRED_FILES[filename]
            output_path = input_dir / filename

            print(f"\n  [{i}/{len(files_to_download)}] Downloading {filename}...")
            print(f"    URL: {url}")

            success = download_file(url, output_path)

            if success:
                size = output_path.stat().st_size
                print(f"    ✓ Saved ({format_size(size)})")
            else:
                print(f"    ✗ Failed to download")
                missing_files.append(filename)

    if missing_files:
        print(f"\n❌ Could not obtain {len(missing_files)} files: {', '.join(missing_files)}")
    else:
        print(f"\n✓ All {len(REQUIRED_FILES)} required files are available")

    return missing_files


def load_tsv(filepath: Path, columns: List[str]) -> pd.DataFrame:
    """Load a ZFIN TSV file with proper column names.

    ZFIN files have: line 1 = date stamp, line 2 = column headers, line 3+ = data.
    The header line has a trailing tab, so we skip both lines and assign names manually.
    """
    try:
        df = pd.read_csv(filepath, sep="\t", header=None, names=columns,
                         skiprows=2, dtype=str, na_values=["", "none"],
                         keep_default_na=True)
        return df
    except Exception as e:
        print(f"Warning: Could not load {filepath}: {e}")
        return pd.DataFrame(columns=columns)


class ZFINImageMetadataExtractor:
    """Extract and compile metadata for ZFIN images."""

    def __init__(self, input_dir: Path):
        self.input_dir = Path(input_dir)
        self.data = {}
        self._load_all_data()
        self._build_indexes()

    def _load_all_data(self):
        """Load all required TSV files into memory."""
        print("\nLoading ZFIN data files into memory...")
        for filename, columns in COLUMN_NAMES.items():
            filepath = self.input_dir / filename
            if filepath.exists():
                self.data[filename] = load_tsv(filepath, columns)
                print(f"  ✓ {filename}: {len(self.data[filename]):,} rows")
            else:
                print(f"  ✗ {filename}: not found")
                self.data[filename] = pd.DataFrame(columns=columns)

    def _build_indexes(self):
        """Pre-build O(1) dict lookups from every DataFrame.

        The original code did df[df[col] == val] inside the per-image loop,
        which is O(n) per lookup and O(n²) overall for 53k images. Building
        dicts once here makes every lookup O(1) and reduces total runtime from
        hours to seconds.
        """
        print("\nBuilding indexes...")

        # image_id → {figure_id, image_preparation}
        self._img_to_fig: Dict[str, Dict] = {}
        for _, row in self.data["ImageFigures.txt"].iterrows():
            self._img_to_fig[row["Image ID"]] = {
                "figure_id": row.get("Figure ID"),
                "image_preparation": row.get("Image Preparation"),
            }

        # figure_id → [(expression_id, expression_result_id), ...]
        self._fig_to_results: Dict[str, List] = {}
        for _, row in self.data["xpatfig_fish.txt"].iterrows():
            fid = row["Figure ID"]
            if fid not in self._fig_to_results:
                self._fig_to_results[fid] = []
            self._fig_to_results[fid].append((row["Expression ID"], row["Expression Result ID"]))

        # expression_id → first matching xpat_fish row (dict)
        self._expr_to_xpat: Dict[str, Dict] = {}
        for _, row in self.data["xpat_fish.txt"].iterrows():
            eid = row["Expression ID"]
            if eid not in self._expr_to_xpat:
                self._expr_to_xpat[eid] = row.to_dict()

        # expression_result_id → [(start_stage_id, anat_super_id, anat_sub_id, expression_found), ...]
        self._result_to_stage_anat: Dict[str, List] = {}
        for _, row in self.data["xpat_stage_anatomy.txt"].iterrows():
            rid = row["Expression Result ID"]
            if rid not in self._result_to_stage_anat:
                self._result_to_stage_anat[rid] = []
            self._result_to_stage_anat[rid].append((
                row.get("Start Stage ID"),
                row.get("Anatomy Super Term ID"),
                row.get("Anatomy Sub Term ID"),
                row.get("Expression Found"),
            ))

        # stage_id → {stage_obo_id, stage_name, begin_hours, end_hours}
        self._stage_id_to_info: Dict[str, Dict] = {}
        for _, row in self.data["stage_ontology.txt"].iterrows():
            self._stage_id_to_info[row["Stage ID"]] = {
                "stage_obo_id": row.get("Stage OBO ID"),
                "stage_name": row.get("Stage Name"),
                "begin_hours": row.get("Begin Hours"),
                "end_hours": row.get("End Hours"),
            }

        # anatomy_id → anatomy_name
        self._anat_id_to_name: Dict[str, str] = {}
        for _, row in self.data["anatomy_item.txt"].iterrows():
            self._anat_id_to_name[row["Anatomy ID"]] = row.get("Anatomy Name")

        # gene_id (ZFIN ID) → {so_id, ncbi_gene_id}
        self._gene_id_to_info: Dict[str, Dict] = {}
        for _, row in self.data["gene.txt"].iterrows():
            self._gene_id_to_info[row["ZFIN ID"]] = {
                "so_id": row.get("SO ID"),
                "ncbi_gene_id": row.get("NCBI Gene ID"),
            }

        # fish_id → {fish_name, fish_abbreviation, genotype_id}
        self._fish_id_to_info: Dict[str, Dict] = {}
        for _, row in self.data["wildtypes_fish.txt"].iterrows():
            self._fish_id_to_info[row["Fish ID"]] = {
                "fish_name": row.get("Fish Name"),
                "fish_abbreviation": row.get("Fish Abbreviation"),
                "genotype_id": row.get("Genotype ID"),
            }

        # environment_id → {zeco_term_name, zeco_term_id, chebi_term_name, chebi_term_id}
        self._env_id_to_info: Dict[str, Dict] = {}
        for _, row in self.data["xpat_environment_fish.txt"].iterrows():
            self._env_id_to_info[row["Environment ID"]] = {
                "zeco_term_name": row.get("ZECO Term Name"),
                "zeco_term_id": row.get("ZECO Term ID"),
                "chebi_term_name": row.get("Chebi Term Name"),
                "chebi_term_id": row.get("Chebi Term ID"),
            }

        # publication_zfin_id → pubmed_id
        self._pub_id_to_pubmed: Dict[str, Any] = {}
        for _, row in self.data["pub_to_pubmed_id_translation.txt"].iterrows():
            self._pub_id_to_pubmed[row["Publication ZFIN ID"]] = row.get("PubMed ID")

        # gene_id → [{human_symbol, human_name, omim_id, hgnc_id, entrez_gene_id}, ...]
        self._gene_id_to_orthologs: Dict[str, List] = {}
        seen_ortho: Dict[str, set] = {}
        for _, row in self.data["human_orthos.txt"].iterrows():
            gid = row["ZFIN ID"]
            sym = row.get("Human Symbol")
            if not sym:
                continue
            if gid not in seen_ortho:
                seen_ortho[gid] = set()
                self._gene_id_to_orthologs[gid] = []
            if sym not in seen_ortho[gid]:
                seen_ortho[gid].add(sym)
                self._gene_id_to_orthologs[gid].append({
                    "human_symbol": sym,
                    "human_name": row.get("Human Name"),
                    "omim_id": row.get("OMIM ID"),
                    "hgnc_id": row.get("HGNC ID"),
                    "entrez_gene_id": row.get("Gene ID"),
                })

        # gene_id → [{do_term_name, do_term_id, omim_term_name, omim_id, human_ortholog_symbol}, ...]
        self._gene_id_to_diseases: Dict[str, List] = {}
        for _, row in self.data["gene2DiseaseViaOrthology.txt"].iterrows():
            gid = row["Zebrafish Gene ID"]
            if gid not in self._gene_id_to_diseases:
                self._gene_id_to_diseases[gid] = []
            self._gene_id_to_diseases[gid].append({
                "do_term_name": row.get("DO Term Name"),
                "do_term_id": row.get("DO Term ID"),
                "omim_term_name": row.get("OMIM Term Name"),
                "omim_id": row.get("OMIM ID"),
                "human_ortholog_symbol": row.get("Human Ortholog Symbol"),
            })

        # gene_id → [uniprot_id, ...]
        self._gene_id_to_uniprot: Dict[str, List] = {}
        for _, row in self.data["uniprot.txt"].iterrows():
            gid = row["ZFIN ID"]
            uid = row.get("UniProt ID")
            if not uid or pd.isna(uid):
                continue
            if gid not in self._gene_id_to_uniprot:
                self._gene_id_to_uniprot[gid] = []
            if uid not in self._gene_id_to_uniprot[gid]:
                self._gene_id_to_uniprot[gid].append(uid)

        print("  ✓ Indexes built")

    def get_image_metadata(self, image_id: str) -> Dict[str, Any]:
        """Extract all metadata for a single image ID using O(1) dict lookups."""
        result = {
            "image_id": image_id,
            "image_info": {},
            "expression": {},
            "gene": {},
            "fish": {},
            "environment": {},
            "publication": {},
            "anatomical_locations": [],
            "developmental_stages": [],
            "human_orthologs": [],
            "disease_associations": [],
            "uniprot_ids": []
        }

        # 1. Basic image info
        img_info = self._img_to_fig.get(image_id)
        if not img_info:
            return result
        figure_id = img_info["figure_id"]
        result["image_info"] = {
            "image_id": image_id,
            "figure_id": figure_id,
            "image_preparation": img_info["image_preparation"],
        }

        # 2. Expression linkage via figure
        # _fig_to_results[figure_id] = [(expression_id, expression_result_id), ...]
        fig_results = self._fig_to_results.get(figure_id)
        if not fig_results:
            return result
        expression_id = fig_results[0][0]
        expression_result_ids = list({r[1] for r in fig_results})

        # 3. Expression details
        xpat_info = self._expr_to_xpat.get(expression_id)
        if not xpat_info:
            return result
        gene_id     = xpat_info.get("Gene ID")
        fish_id     = xpat_info.get("Fish ID")
        env_id      = xpat_info.get("Environment ID")
        pub_id      = xpat_info.get("Publication ID")
        gene_symbol = xpat_info.get("Gene Symbol")
        result["expression"] = {
            "expression_id": expression_id,
            "expression_type": xpat_info.get("Expression Type"),
            "expression_type_mmo_id": xpat_info.get("Expression Type MMO ID"),
            "est_id": xpat_info.get("EST ID"),
            "est_symbol": xpat_info.get("EST Symbol"),
            "probe_quality": xpat_info.get("Probe Quality"),
        }

        # 4. Gene details
        gene_info = self._gene_id_to_info.get(gene_id, {})
        result["gene"] = {
            "gene_id": gene_id,
            "gene_symbol": gene_symbol,
            "so_id": gene_info.get("so_id"),
            "ncbi_gene_id": gene_info.get("ncbi_gene_id"),
        }

        # 5. Fish details
        fish_info = self._fish_id_to_info.get(fish_id, {})
        result["fish"] = {
            "fish_id": fish_id,
            "fish_name": fish_info.get("fish_name"),
            "fish_abbreviation": fish_info.get("fish_abbreviation"),
            "genotype_id": fish_info.get("genotype_id"),
        }

        # 6. Environment details
        env_info = self._env_id_to_info.get(env_id, {})
        result["environment"] = {
            "environment_id": env_id,
            "zeco_term_name": env_info.get("zeco_term_name"),
            "zeco_term_id": env_info.get("zeco_term_id"),
            "chebi_term_name": env_info.get("chebi_term_name"),
            "chebi_term_id": env_info.get("chebi_term_id"),
        }

        # 7. Publication details
        result["publication"] = {
            "publication_id": pub_id,
            "pubmed_id": self._pub_id_to_pubmed.get(pub_id),
        }

        # 8. Stage and anatomy — joined via expression_result_ids (figure-specific).
        # This is the correctness fix: using expression_result_ids instead of expression_id
        # gives per-image stage/anatomy data rather than the whole-experiment union.
        stages_seen = set()
        anatomies_seen = set()
        for rid in expression_result_ids:
            for (start_sid, anat_super_id, anat_sub_id, expr_found) in \
                    self._result_to_stage_anat.get(rid, []):

                # Stage — Start Stage ID only (the stage this result was observed at)
                if start_sid and start_sid not in stages_seen:
                    stages_seen.add(start_sid)
                    s = self._stage_id_to_info.get(start_sid)
                    if s:
                        result["developmental_stages"].append({
                            "stage_id": start_sid,
                            "stage_obo_id": s["stage_obo_id"],
                            "stage_name": s["stage_name"],
                            "begin_hours": s["begin_hours"],
                            "end_hours": s["end_hours"],
                        })

                # Anatomy
                for anat_id in [anat_super_id, anat_sub_id]:
                    if anat_id and anat_id not in anatomies_seen:
                        anatomies_seen.add(anat_id)
                        anat_name = self._anat_id_to_name.get(anat_id)
                        if anat_name:
                            result["anatomical_locations"].append({
                                "anatomy_id": anat_id,
                                "anatomy_name": anat_name,
                                "expression_found": expr_found,
                            })

        # 9. Human orthologs
        result["human_orthologs"] = self._gene_id_to_orthologs.get(gene_id, [])

        # 10. Disease associations
        result["disease_associations"] = self._gene_id_to_diseases.get(gene_id, [])

        # 11. UniProt IDs
        result["uniprot_ids"] = self._gene_id_to_uniprot.get(gene_id, [])

        return result

    def get_image_ids_for_publications(self, pub_ids: List[str]) -> List[str]:
        """Resolve publication IDs to image IDs via pub → expression → figure → image chain."""
        # pub → expression IDs
        xpat_df = self.data["xpat_fish.txt"]
        expr_ids = xpat_df[xpat_df["Publication ID"].isin(pub_ids)]["Expression ID"].unique()
        print(f"  Found {len(expr_ids):,} expression IDs for {len(pub_ids)} publications")

        # expression → figure IDs
        xpatfig_df = self.data["xpatfig_fish.txt"]
        fig_ids = xpatfig_df[xpatfig_df["Expression ID"].isin(expr_ids)]["Figure ID"].unique()
        print(f"  Found {len(fig_ids):,} figure IDs")

        # figure → image IDs
        img_df = self.data["ImageFigures.txt"]
        image_ids = img_df[img_df["Figure ID"].isin(fig_ids)]["Image ID"].unique().tolist()
        print(f"  Found {len(image_ids):,} image IDs")

        return image_ids

    def extract_all_images(self, image_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Extract metadata for multiple images (or all images if none specified)."""
        if image_ids is None:
            image_ids = self.data["ImageFigures.txt"]["Image ID"].unique().tolist()

        results = []
        total = len(image_ids)
        print(f"\nExtracting metadata for {total:,} images...")

        start_time = time.time()
        for i, image_id in enumerate(image_ids):
            if (i + 1) % 5000 == 0 or (i + 1) == total:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                eta = (total - i - 1) / rate if rate > 0 else 0
                print(f"  Progress: {i + 1:,}/{total:,} ({(i+1)/total*100:.1f}%) - {rate:.0f} img/s - ETA: {eta:.0f}s")
            results.append(self.get_image_metadata(image_id))

        return results

    def results_to_dataframe(self, results: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert nested results to a flat DataFrame for TSV output."""
        flat_rows = []

        for r in results:
            row = {
                "image_id": r["image_id"],
                "figure_id": r["image_info"].get("figure_id"),
                "image_preparation": r["image_info"].get("image_preparation"),
                "expression_id": r["expression"].get("expression_id"),
                "expression_type": r["expression"].get("expression_type"),
                "expression_type_mmo_id": r["expression"].get("expression_type_mmo_id"),
                "est_id": r["expression"].get("est_id"),
                "est_symbol": r["expression"].get("est_symbol"),
                "probe_quality": r["expression"].get("probe_quality"),
                "gene_id": r["gene"].get("gene_id"),
                "gene_symbol": r["gene"].get("gene_symbol"),
                "gene_so_id": r["gene"].get("so_id"),
                "ncbi_gene_id": r["gene"].get("ncbi_gene_id"),
                "fish_id": r["fish"].get("fish_id"),
                "fish_name": r["fish"].get("fish_name"),
                "fish_abbreviation": r["fish"].get("fish_abbreviation"),
                "genotype_id": r["fish"].get("genotype_id"),
                "environment_id": r["environment"].get("environment_id"),
                "zeco_term_name": r["environment"].get("zeco_term_name"),
                "zeco_term_id": r["environment"].get("zeco_term_id"),
                "publication_id": r["publication"].get("publication_id"),
                "pubmed_id": r["publication"].get("pubmed_id"),
                "anatomical_locations": "|".join([
                    f"{a['anatomy_id']}:{a['anatomy_name']}" 
                    for a in r["anatomical_locations"] if a.get("anatomy_name")
                ]),
                "developmental_stages": "|".join([
                    f"{s['stage_id']}:{s['stage_name']}({s.get('begin_hours', '?')}-{s.get('end_hours', '?')}hpf)"
                    for s in r["developmental_stages"] if s.get("stage_name")
                ]),
                "human_orthologs": "|".join([
                    f"{o['human_symbol']}(OMIM:{o.get('omim_id', 'N/A')})"
                    for o in r["human_orthologs"] if o.get("human_symbol")
                ]),
                "disease_associations": "|".join([
                    f"{d['do_term_name']}(DO:{d.get('do_term_id', 'N/A')})"
                    for d in r["disease_associations"] if d.get("do_term_name")
                ]),
                "uniprot_ids": "|".join(r["uniprot_ids"][:10])  # Limit to first 10
            }
            flat_rows.append(row)

        return pd.DataFrame(flat_rows)


def main():
    parser = argparse.ArgumentParser(
        description="Extract metadata for ZFIN images (auto-downloads required files)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--input-dir", "-i", type=Path, default=Path("./zfin_data"),
        help="Directory for ZFIN TSV files (default: ./zfin_data)"
    )
    parser.add_argument(
        "--output-prefix", "-o", type=str, default="image_metadata",
        help="Prefix for output files (default: image_metadata)"
    )
    parser.add_argument(
        "--image-ids", "-ids", type=str, default=None,
        help="Comma-separated list of image IDs to process (default: all images)"
    )
    parser.add_argument(
        "--pub-ids", "-p", type=str, default=None,
        help="Comma-separated publication IDs to filter images by (default: Thisse publications)"
    )
    parser.add_argument(
        "--all-images", action="store_true",
        help="Process all images instead of filtering by publication"
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Disable auto-download of missing files"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Only download files, don't process images"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ZFIN Image Metadata Extractor")
    print("=" * 60)

    # Ensure required files are available
    missing = ensure_files_available(args.input_dir, auto_download=not args.no_download)

    if missing:
        print(f"\n❌ Cannot proceed without required files.")
        return 1

    if args.download_only:
        print("\n✓ Download complete. Exiting (--download-only mode).")
        return 0

    # Extract metadata
    extractor = ZFINImageMetadataExtractor(args.input_dir)

    # Determine which images to process
    image_ids = None
    if args.image_ids:
        image_ids = [id.strip() for id in args.image_ids.split(",")]
        print(f"\nProcessing {len(image_ids)} specified image(s)")
    elif not args.all_images:
        # Default: filter by publication IDs (Thisse publications)
        default_pub_ids = [
            "ZDB-PUB-040907-1",   # Thisse 2004
            "ZDB-PUB-010810-1",   # Thisse 2001
            "ZDB-PUB-051025-1",   # Thisse 2005
            "ZDB-PUB-080227-22",  # Thisse 2008
            "ZDB-PUB-080220-1",   # Thisse 2008-2
        ]
        if args.pub_ids:
            pub_ids = [p.strip() for p in args.pub_ids.split(",")]
        else:
            pub_ids = default_pub_ids
        print(f"\nFiltering by {len(pub_ids)} publication(s):")
        for pid in pub_ids:
            print(f"  - {pid}")
        image_ids = extractor.get_image_ids_for_publications(pub_ids)

    results = extractor.extract_all_images(image_ids)

    # Save JSON output
    json_path = f"{args.output_prefix}.json"
    print(f"\nSaving JSON output to: {json_path}")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    json_size = Path(json_path).stat().st_size
    print(f"  ✓ Saved ({format_size(json_size)})")

    # Save TSV output
    tsv_path = f"{args.output_prefix}.tsv"
    print(f"\nSaving TSV output to: {tsv_path}")
    df = extractor.results_to_dataframe(results)
    df.to_csv(tsv_path, sep="\t", index=False)
    tsv_size = Path(tsv_path).stat().st_size
    print(f"  ✓ Saved ({format_size(tsv_size)})")

    print("\n" + "=" * 60)
    print(f"✓ Complete! Processed {len(results):,} images")
    print(f"  Output files: {json_path}, {tsv_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
