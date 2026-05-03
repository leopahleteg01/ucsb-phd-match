import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
MASTER_JSON = BASE / 'ucsb_professors_master.json'
PROFILES_JSON = BASE / 'ucsb_professor_profiles.json'
SHORTLIST_JSON = BASE / 'ucsb_professor_shortlist_cards.json'

master = json.loads(MASTER_JSON.read_text())
profiles = json.loads(PROFILES_JSON.read_text()) if PROFILES_JSON.exists() else []
profiles_by_name = {p.get('name', ''): p for p in profiles}


def _compact_text(value, limit=220):
    text = (value or '').strip()
    return text[:limit]


def _strength_lines(p, prof):
    lines = []
    methods = (p.get('methods_keywords', []) or [])[:4]
    applications = (p.get('application_keywords', []) or [])[:4]
    topics = (p.get('topic_clusters', []) or [])[:3]
    pubs = (p.get('selected_publication_mentions', []) or [])[:2]
    if methods:
        lines.append('Methods: ' + ', '.join(methods))
    if applications:
        lines.append('Applications: ' + ', '.join(applications))
    if topics:
        lines.append('Topics: ' + ', '.join(topics))
    if pubs:
        lines.append('Publication signals: ' + ' | '.join(_compact_text(x, 120) for x in pubs))
    return lines[:4]


cards = []
for p in master:
    prof = profiles_by_name.get(p.get('name', ''), {})
    profile = prof.get('profile', {}) if isinstance(prof, dict) else {}
    focus = (
        _compact_text(profile.get('professor_focus_detailed', ''), 260)
        or _compact_text(profile.get('research_summary_long', ''), 220)
        or _compact_text(profile.get('research_summary_short', ''), 180)
    )
    cards.append({
        'professor_id': p.get('professor_id', ''),
        'name': p.get('name', ''),
        'department': p.get('department', ''),
        'title': p.get('title', ''),
        'focus': focus,
        'methods': (profile.get('methods_keywords', []) or [])[:8],
        'applications': (profile.get('application_keywords', []) or [])[:8],
        'research_keywords': (profile.get('research_keywords', []) or [])[:8],
        'topic_clusters': (profile.get('topic_clusters', []) or [])[:6],
        'strength_lines': _strength_lines(p, prof),
        'summary_short': _compact_text(profile.get('research_summary_short', ''), 180),
        'source_quality': profile.get('source_quality', ''),
        'links': prof.get('links', {}),
    })

SHORTLIST_JSON.write_text(json.dumps(cards, ensure_ascii=False, indent=2))
print(f'wrote {SHORTLIST_JSON}')
print(f'cards: {len(cards)}')
