import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
MASTER_JSON = BASE / 'ucsb_professors_master.json'
PROFILES_JSON = BASE / 'ucsb_professor_profiles.json'

master = json.loads(MASTER_JSON.read_text())
profiles = []
for p in master:
    profiles.append({
        'professor_id': p.get('professor_id',''),
        'name': p.get('name',''),
        'faculty': p.get('department',''),
        'affiliations': p.get('affiliations', []),
        'title': p.get('title',''),
        'email': p.get('email',''),
        'links': {
            'ucsb_profile': p.get('ucsb_profile_url',''),
            'personal_website': p.get('personal_website_url',''),
            'lab_website': p.get('lab_website_url',''),
            'other_personal_links': [x for x in [
                p.get('personal_website_url',''),
                p.get('lab_website_url','')
            ] if x],
            'google_scholar': p.get('google_scholar_url_guess',''),
            'google_scholar_query': p.get('google_scholar_query',''),
            'official_query': p.get('google_query_official',''),
            'personal_query': p.get('google_query_personal',''),
            'lab_query': p.get('google_query_lab',''),
        },
        'profile': {
            'research_summary_short': p.get('research_summary_short',''),
            'research_summary_long': p.get('research_summary_long',''),
            'deep_profile_text': p.get('deep_profile_text',''),
            'research_keywords': p.get('research_keywords', []),
            'topic_clusters': p.get('topic_clusters', []),
            'affiliated_centers': p.get('affiliated_centers', []),
            'affiliated_labs': p.get('affiliated_labs', []),
            'theory_to_application_spectrum': p.get('theory_to_application_spectrum',''),
            'source_quality': p.get('source_quality',''),
            'website_status': p.get('website_status',''),
            'scholar_status': p.get('scholar_status','')
        }
    })

PROFILES_JSON.write_text(json.dumps(profiles, ensure_ascii=False, indent=2))
print(f'wrote {PROFILES_JSON}')
print(f'profiles: {len(profiles)}')
