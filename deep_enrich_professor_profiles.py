import json
import re
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
MASTER_JSON = BASE / 'ucsb_professors_master.json'
MASTER_CSV = BASE / 'ucsb_professors_master.csv'
PUBLISH_JSON = BASE / 'ucsb_professor_screening.json'

BAD_CONTENT_BITS = [
    'home people', 'contact address', 'harold frank hall', 'campus affiliations', 'external publications',
    'ucsb publications', 'phone', 'personal website', 'education', 'affiliations affiliations',
    'me research areas', 'research areas', 'people faculty', 'skip to main content'
]
PUBLICATION_WORDS = ['publication', 'publications', 'paper', 'papers', 'journal', 'conference', 'proceedings', 'scholar']
METHOD_TERMS = ['control', 'optimization', 'learning', 'reinforcement learning', 'machine learning', 'vision', 'simulation', 'modeling', 'planning', 'estimation', 'formal methods', 'graphics', 'hci', 'security', 'networking']
APPLICATION_TERMS = ['robotics', 'autonomy', 'digital twins', 'cybersecurity', 'virtual reality', 'augmented reality', 'communications', 'power systems', 'manufacturing', 'human-computer interaction', 'medical', 'wireless', 'sensing', 'mobility']
HONOR_WORDS = ['award', 'honor', 'fellow', 'career', 'best paper', 'distinguished']
CENTER_WORDS = ['center', 'institute', 'laboratory', 'lab', 'program', 'project']
SOURCE_LABELS = [
    ('ucsb_profile_url', 'ucsb_profile'),
    ('personal_website_url', 'personal_website'),
    ('lab_website_url', 'lab_website'),
]
EXTRA_LINK_FIELDS = [
    'other_personal_links',
]


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', 'ignore')


def strip_tags(text):
    text = re.sub(r'<script.*?</script>', ' ', text, flags=re.S|re.I)
    text = re.sub(r'<style.*?</style>', ' ', text, flags=re.S|re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def clean_profile_text(text):
    text = strip_tags(text)
    for bad in BAD_CONTENT_BITS:
        text = re.sub(re.escape(bad), ' ', text, flags=re.I)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', ' ', text)
    text = re.sub(r'\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,;.-')
    return text


def extract_main_text(html):
    candidates = []
    for pattern in [r'<main[^>]*>(.*?)</main>', r'<article[^>]*>(.*?)</article>', r'<section[^>]*>(.*?)</section>']:
        for chunk in re.findall(pattern, html, re.S|re.I):
            text = clean_profile_text(chunk)
            if len(text) > 200:
                candidates.append(text)
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S|re.I)
    cleaned = [clean_profile_text(p) for p in paras]
    cleaned = [p for p in cleaned if len(p) > 40]
    if cleaned:
        candidates.append(' '.join(cleaned[:16]).strip())
    div_blocks = re.findall(r'<div[^>]*>(.*?)</div>', html, re.S|re.I)
    div_clean = [clean_profile_text(d) for d in div_blocks]
    div_clean = [d for d in div_clean if len(d) > 120]
    if div_clean:
        candidates.append(' '.join(div_clean[:10]).strip())
    candidates = sorted(candidates, key=len, reverse=True)
    return candidates[0][:7000].strip() if candidates else ''


def sentence_chunks(text):
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def extract_publication_signals(text):
    parts = sentence_chunks(text)
    hits = [p for p in parts if any(w in p.lower() for w in PUBLICATION_WORDS)]
    return hits[:8]


def extract_focus_sentences(text):
    parts = sentence_chunks(text)
    focus = []
    for p in parts:
        pl = p.lower()
        if any(x in pl for x in ['research interests', 'research focuses', 'work focuses', 'my work focuses', 'research lies', 'focus on', 'works on', 'research includes', 'studies', 'develops']):
            focus.append(p)
    if not focus:
        focus = parts[:3]
    return focus[:5]


def extract_term_hits(text, terms):
    tl = text.lower()
    return [t for t in terms if t in tl]


def extract_honor_sentences(text):
    parts = sentence_chunks(text)
    return [p for p in parts if any(w in p.lower() for w in HONOR_WORDS)][:5]


def extract_affiliation_signals(text):
    parts = sentence_chunks(text)
    return [p for p in parts if any(w in p.lower() for w in CENTER_WORDS)][:6]


def load_master():
    return json.loads(MASTER_JSON.read_text())


def merge_unique(items, limit=None):
    out = []
    seen = set()
    for item in items:
        if not item:
            continue
        key = item.strip() if isinstance(item, str) else json.dumps(item, sort_keys=True, ensure_ascii=False)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if limit and len(out) >= limit:
            break
    return out


def source_domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ''


def collect_source_payload(rec):
    sources = []
    seen_urls = set()
    candidate_sources = []
    for field, label in SOURCE_LABELS:
        url = (rec.get(field) or '').strip()
        if url:
            candidate_sources.append((label, url))
    for field in EXTRA_LINK_FIELDS:
        vals = rec.get(field) or []
        if isinstance(vals, str):
            vals = [vals]
        for url in vals:
            url = (url or '').strip()
            if url:
                candidate_sources.append((field, url))
    for label, url in candidate_sources:
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            html = fetch(url)
            text = extract_main_text(html)
            if text:
                sources.append({
                    'label': label,
                    'url': url,
                    'domain': source_domain(url),
                    'text': text[:6500],
                })
            else:
                sources.append({
                    'label': label,
                    'url': url,
                    'domain': source_domain(url),
                    'error': 'no extractable text found',
                })
        except Exception as e:
            sources.append({
                'label': label,
                'url': url,
                'domain': source_domain(url),
                'error': str(e),
            })
    return sources


def save_master(master):
    MASTER_JSON.write_text(json.dumps(master, ensure_ascii=False, indent=2))
    import csv
    fieldnames = sorted({k for rec in master for k in rec.keys()}) if master else []
    with MASTER_CSV.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for rec in master:
            row = dict(rec)
            for k, v in row.items():
                if isinstance(v, list):
                    row[k] = json.dumps(v, ensure_ascii=False)
            w.writerow(row)


def save_publish(master):
    rows = []
    for p in master:
        rows.append({
            'name': p.get('name',''),
            'department': p.get('department',''),
            'affiliations': p.get('affiliations', []),
            'title': p.get('title',''),
            'email': p.get('email',''),
            'primary_areas': p.get('research_summary_short',''),
            'comparison_summary': p.get('research_summary_long',''),
            'notes': ', '.join(p.get('research_keywords', [])[:20]),
            'ucsb_profile_url': p.get('ucsb_profile_url',''),
            'website_guess': p.get('personal_website_url','') or p.get('lab_website_url',''),
            'personal_website_url': p.get('personal_website_url',''),
            'lab_website_url': p.get('lab_website_url',''),
            'website_status': p.get('website_status',''),
            'website_domain': p.get('website_domain',''),
            'google_scholar_query': p.get('google_scholar_query',''),
            'google_scholar_url_guess': p.get('google_scholar_url_guess',''),
            'scholar_status': p.get('scholar_status',''),
            'google_query_official': p.get('google_query_official',''),
            'google_query_personal': p.get('google_query_personal',''),
            'deep_profile_text': p.get('deep_profile_text',''),
            '_blob': ' | '.join([
                p.get('name',''), p.get('department',''), p.get('title',''), p.get('email',''),
                p.get('research_summary_short',''), p.get('research_summary_long',''),
                p.get('personal_website_url',''), p.get('lab_website_url',''),
                p.get('google_scholar_query',''), ' '.join(p.get('research_keywords', []) or [])
            ]).lower()
        })
    PUBLISH_JSON.write_text(json.dumps(rows, ensure_ascii=False))


def enrich(master):
    for rec in master:
        sources = collect_source_payload(rec)
        usable_sources = [s for s in sources if s.get('text')]
        if not usable_sources:
            continue
        combined_text = ' '.join(s.get('text', '') for s in usable_sources).strip()
        if not combined_text:
            continue
        rec['profile_source_records'] = [{
            'label': s.get('label', ''),
            'url': s.get('url', ''),
            'domain': s.get('domain', ''),
            'text_excerpt': s.get('text', '')[:500],
            'error': s.get('error', ''),
        } for s in sources]
        rec['source_domains'] = merge_unique([s.get('domain', '') for s in usable_sources], limit=10)
        rec['deep_profile_text'] = combined_text[:6000]
        sentences = sentence_chunks(combined_text)
        focus_sentences = extract_focus_sentences(combined_text)
        pub_signals = extract_publication_signals(combined_text)
        method_hits = extract_term_hits(combined_text, METHOD_TERMS)
        application_hits = extract_term_hits(combined_text, APPLICATION_TERMS)
        honor_signals = extract_honor_sentences(combined_text)
        affiliation_signals = extract_affiliation_signals(combined_text)
        if focus_sentences:
            rec['research_summary_long'] = ' '.join(focus_sentences)[:1200]
            rec['professor_focus_detailed'] = ' '.join(focus_sentences)[:1800]
        elif sentences:
            rec['research_summary_long'] = ' '.join(sentences[:4])[:1200]
            rec['professor_focus_detailed'] = ' '.join(sentences[:5])[:1800]
        rec['selected_publication_mentions'] = merge_unique(pub_signals, limit=8)
        rec['publication_signal_notes'] = ' | '.join(rec['selected_publication_mentions'][:6])
        rec['methods_keywords'] = merge_unique((rec.get('methods_keywords', []) or []) + method_hits, limit=16)
        rec['application_keywords'] = merge_unique((rec.get('application_keywords', []) or []) + application_hits, limit=16)
        rec['honors_highlights'] = merge_unique(honor_signals, limit=8)
        rec['affiliation_signal_sentences'] = merge_unique(affiliation_signals, limit=8)
        rec['rich_evidence_snippets'] = merge_unique(focus_sentences + pub_signals + honor_signals + affiliation_signals, limit=18)
        rec['fit_signal_summary'] = {
            'methods': rec['methods_keywords'][:16],
            'applications': rec['application_keywords'][:16],
            'honors_count': len(rec['honors_highlights']),
            'publication_signal_count': len(rec['selected_publication_mentions']),
            'source_domains': rec.get('source_domains', []),
            'source_count': len(usable_sources),
        }
        rec['extraction_notes'] = 'Deep-enriched from multiple sources including UCSB profile and linked personal/lab pages when available.'
        deep_len = len(rec.get('deep_profile_text', ''))
        if len(usable_sources) >= 2 and deep_len >= 1800:
            rec['source_quality'] = 'high'
        elif deep_len >= 900:
            rec['source_quality'] = 'medium_high'
        elif deep_len >= 250:
            rec['source_quality'] = 'medium'
        else:
            rec['source_quality'] = rec.get('source_quality', 'low') or 'low'
    return master


if __name__ == '__main__':
    master = load_master()
    master = enrich(master)
    save_master(master)
    save_publish(master)
    print('deep enrichment complete')
