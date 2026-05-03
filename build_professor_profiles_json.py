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
            'professor_focus_detailed': p.get('professor_focus_detailed',''),
            'deep_profile_text': p.get('deep_profile_text',''),
            'research_keywords': p.get('research_keywords', []),
            'methods_keywords': p.get('methods_keywords', []),
            'application_keywords': p.get('application_keywords', []),
            'topic_clusters': p.get('topic_clusters', []),
            'affiliated_centers': p.get('affiliated_centers', []),
            'affiliated_labs': p.get('affiliated_labs', []),
            'affiliation_signal_sentences': p.get('affiliation_signal_sentences', []),
            'selected_publication_mentions': p.get('selected_publication_mentions', []),
            'publication_signal_notes': p.get('publication_signal_notes',''),
            'honors_highlights': p.get('honors_highlights', []),
            'fit_signal_summary': p.get('fit_signal_summary', {}),
            'theory_to_application_spectrum': p.get('theory_to_application_spectrum',''),
            'source_quality': p.get('source_quality',''),
            'source_domains': p.get('source_domains', []),
            'profile_source_records': p.get('profile_source_records', []),
            'rich_evidence_snippets': p.get('rich_evidence_snippets', []),
            'extraction_notes': p.get('extraction_notes', ''),
            'website_status': p.get('website_status',''),
            'scholar_status': p.get('scholar_status','')
        }
    })

PROFILES_JSON.write_text(json.dumps(profiles, ensure_ascii=False, indent=2))
print(f'wrote {PROFILES_JSON}')
print(f'profiles: {len(profiles)}')
