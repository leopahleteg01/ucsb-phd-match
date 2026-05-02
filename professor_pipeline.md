# UCSB Professor Pipeline

## Purpose
This is the automated end-to-end pipeline for building the UCSB professor dataset.

It produces:
- `ucsb_professors_master.csv`
- `ucsb_professors_master.json`
- `ucsb_professor_connections.json`
- `ucsb_professor_screening.json`

## What it does
1. Builds a neutral professor master from the legacy roster.
2. Enriches it from the official UCSB faculty list pages.
3. Deep-enriches it from individual UCSB professor profile pages.
4. Publishes a frontend-ready JSON dataset.

## Run
```bash
python3 run_professor_pipeline.py
```

## Current component scripts
- `build_professor_master.py`
- `enrich_professor_master.py`
- `deep_enrich_professor_profiles.py`
- `build_publish_json.py`

## Notes
- The current Google Scholar pipeline is query-first, not citation-metrics scraping.
- Website pipeline now tracks presence, domain, and personal/lab URL fields.
- Deep profile enrichment improves long summaries, but some profile pages still need cleaner sentence selection.
- This pipeline is now the canonical path for regenerating professor data.
