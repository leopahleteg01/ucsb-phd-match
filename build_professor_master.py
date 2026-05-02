import csv
import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
INPUT = BASE / 'ucsb_professor_screening.csv'
MASTER_CSV = BASE / 'ucsb_professors_master.csv'
MASTER_JSON = BASE / 'ucsb_professors_master.json'
GRAPH_JSON = BASE / 'ucsb_professor_connections.json'

STOP = {
    'and','the','for','with','from','into','through','using','based','their','this','that','than','less','more','very','best','good',
    'strong','option','route','work','works','useful','interesting','direct','general','systems','system','engineering','research'
}


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')


def split_keywords(*parts):
    raw = ' ; '.join([p for p in parts if p])
    toks = [t.strip().lower() for t in re.split(r'[;,|/\n]+', raw) if t.strip()]
    out = []
    for t in toks:
        if len(t) < 3 or t in STOP:
            continue
        if t not in out:
            out.append(t)
    return out


def clean_text(text):
    return re.sub(r'\s+', ' ', (text or '')).strip()

rows = list(csv.DictReader(INPUT.open()))
master = []
for r in rows:
    name = r['name'].strip()
    keywords = split_keywords(r.get('primary_areas',''), r.get('research_guess',''))
    research_short = clean_text(r.get('primary_areas',''))
    research_long = clean_text(' '.join(filter(None, [r.get('research_guess',''), r.get('comparison_summary',''), r.get('notes','')])))
    dept = clean_text(r.get('department',''))
    affiliations = [x.strip() for x in re.split(r'/', dept) if x.strip()] if dept else []
    personal_site = clean_text(r.get('website_guess',''))
    record = {
        'professor_id': slugify(name),
        'name': name,
        'department': dept,
        'affiliations': affiliations,
        'title': clean_text(r.get('title_guess','')),
        'email': clean_text(r.get('email','')),
        'ucsb_profile_url': clean_text(r.get('ucsb_profile_url','')),
        'personal_website_url': personal_site,
        'lab_website_url': personal_site,
        'google_scholar_query': clean_text(r.get('google_query_scholar','')),
        'google_scholar_url_guess': '',
        'google_query_official': clean_text(r.get('google_query_official','')),
        'google_query_personal': clean_text(r.get('google_query_personal','')),
        'google_query_lab': f'{name} UCSB lab website',
        'status': clean_text(r.get('current_status','')) or 'imported',
        'source_quality': 'medium',
        'research_summary_short': research_short,
        'research_summary_long': research_long,
        'research_areas_raw': clean_text(r.get('primary_areas','')),
        'research_keywords': keywords,
        'methods_keywords': [],
        'application_keywords': [],
        'theory_to_application_spectrum': '',
        'publication_signal_notes': '',
        'lab_signal_notes': '',
        'student_signal_notes': '',
        'department_links': affiliations,
        'affiliated_centers': [],
        'affiliated_labs': [],
        'collaborator_name_guesses': [],
        'research_overlap_groups': [],
        'topic_clusters': [],
        'cross_appointments': affiliations[1:] if len(affiliations) > 1 else [],
        'inferred_peer_set': [],
        'ucsb_profile_source': clean_text(r.get('ucsb_profile_url','')),
        'personal_site_source': personal_site,
        'lab_site_source': personal_site,
        'scholar_source': clean_text(r.get('google_query_scholar','')),
        'notes_source': 'legacy ucsb_professor_screening.csv import',
        'scrape_timestamp': '',
        'extraction_notes': 'Imported from legacy robotics-biased screening dataset; needs neutral enrichment pass.'
    }
    master.append(record)

keyword_index = defaultdict(list)
for rec in master:
    for kw in rec['research_keywords']:
        keyword_index[kw].append(rec['professor_id'])

connections = []
by_id = {r['professor_id']: r for r in master}
for rec in master:
    overlaps = defaultdict(int)
    for kw in rec['research_keywords']:
        for other in keyword_index[kw]:
            if other != rec['professor_id']:
                overlaps[other] += 1
    peers = sorted(overlaps.items(), key=lambda x: (-x[1], x[0]))[:12]
    rec['inferred_peer_set'] = [pid for pid, _ in peers]
    rec['research_overlap_groups'] = [kw for kw in rec['research_keywords'][:8]]
    rec['topic_clusters'] = rec['research_keywords'][:6]
    for pid, score in peers:
        connections.append({
            'source_professor_id': rec['professor_id'],
            'target_professor_id': pid,
            'target_name': by_id[pid]['name'],
            'connection_type': 'keyword_overlap',
            'weight': score,
            'shared_keywords': [kw for kw in rec['research_keywords'] if kw in by_id[pid]['research_keywords']][:10]
        })

fieldnames = list(master[0].keys()) if master else []
with MASTER_CSV.open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for rec in master:
        row = dict(rec)
        for k, v in row.items():
            if isinstance(v, list):
                row[k] = json.dumps(v, ensure_ascii=False)
        w.writerow(row)

MASTER_JSON.write_text(json.dumps(master, ensure_ascii=False, indent=2))
GRAPH_JSON.write_text(json.dumps(connections, ensure_ascii=False, indent=2))

print(f'wrote {MASTER_CSV}')
print(f'wrote {MASTER_JSON}')
print(f'wrote {GRAPH_JSON}')
print(f'professors: {len(master)}')
print(f'connections: {len(connections)}')
