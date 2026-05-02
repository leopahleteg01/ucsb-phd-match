# UCSB General Professor Intelligence Pipeline

## Goal
Build a domain-agnostic professor intelligence pipeline for UCSB faculty across CS, ECE, ME, and related affiliates.

This should not assume robotics, AI, controls, or any other single lens.
It should preserve full professor information and support many user intents:
- theory / math
- robotics / autonomy
- VR / AR / graphics
- cybersecurity
- ML / NLP / vision
- systems
- general exploration

## Core Principle
Separate **raw professor intelligence** from **user-specific ranking**.

The current CSV mixes professor facts with one user-specific robotics fit lens.
That should become only one downstream view, not the master record.

## New Data Layers

### 1. Canonical professor registry
One row per professor with neutral identity fields:
- professor_id
- name
- department
- affiliations
- title
- email
- ucsb_profile_url
- personal_website_url
- lab_website_url
- google_scholar_query
- google_scholar_url_guess
- google_query_official
- google_query_personal
- google_query_lab
- status
- source_quality

### 2. Neutral research profile
General-purpose descriptive fields:
- research_summary_short
- research_summary_long
- research_areas_raw
- research_keywords
- methods_keywords
- application_keywords
- theory_to_application_spectrum
- publication_signal_notes
- lab_signal_notes
- student_signal_notes

### 3. Link graph / connection layer
Store broad relationship signals:
- department_links
- affiliated_centers
- affiliated_labs
- collaborator_name_guesses
- research_overlap_groups
- topic_clusters
- cross_appointments
- inferred_peer_set

### 4. Source provenance layer
Per professor, keep evidence origins:
- ucsb_profile_source
- personal_site_source
- lab_site_source
- scholar_source
- notes_source
- scrape_timestamp
- extraction_notes

### 5. User-specific ranking views
These are generated views, not canonical truth:
- robotics fit
- theory fit
- VR fit
- cybersecurity fit
- custom user notes fit

## Output Artifacts

### Neutral master CSV
`ucsb_professors_master.csv`

### Neutral master JSON
`ucsb_professors_master.json`

### Connection graph JSON
`ucsb_professor_connections.json`

### Optional derived views
- `ucsb_rank_view_robotics.json`
- `ucsb_rank_view_theory.json`
- `ucsb_rank_view_vr.json`
- `ucsb_rank_view_cybersecurity.json`

## Enrichment Targets Per Professor
For each professor, aim to capture:
- official UCSB profile
- title / department / email
- personal website if any
- lab website if any
- general research description
- keyword set
- scholar query
- broad topic cluster(s)
- neutral notes
- related professors by overlap

## Matching / Connection Ideas
Build connections by:
- shared department
- shared keywords
- shared methods
- shared applications
- shared labs or centers
- shared theory/application orientation
- shared webpage/lab references

## Immediate Next Implementation
1. Convert current roster into a neutral master schema.
2. Preserve existing source URLs and query fields.
3. Strip user-specific robotics framing from the canonical master artifact.
4. Generate keyword-based overlap graph.
5. Keep the old screening CSV as a derived legacy view, not the main truth.

## Important Note
The current live app can keep working while this pipeline is built.
But for general-purpose correctness, the app should eventually rank from the new neutral master data, not the robotics-biased CSV.
