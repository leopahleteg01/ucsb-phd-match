import json
from pathlib import Path

base = Path('/data/.openclaw/workspace')
master = json.loads((base / 'ucsb_professors_master.json').read_text())
publish = []
for p in master:
    publish.append({
        'name': p.get('name',''),
        'department': p.get('department',''),
        'affiliations': p.get('affiliations', []),
        'title': p.get('title',''),
        'primary_areas': p.get('research_summary_short',''),
        'comparison_summary': p.get('research_summary_long',''),
        'notes': ', '.join(p.get('research_keywords', [])[:12]),
        'ucsb_profile_url': p.get('ucsb_profile_url',''),
        'website_guess': p.get('personal_website_url','') or p.get('lab_website_url',''),
        '_blob': ' | '.join([
            p.get('name',''),
            p.get('department',''),
            p.get('research_summary_short',''),
            p.get('research_summary_long',''),
            ' '.join(p.get('research_keywords', []) or [])
        ]).lower()
    })
(base / 'ucsb_professor_screening.json').write_text(json.dumps(publish, ensure_ascii=False))
print('wrote publish json from neutral master')
