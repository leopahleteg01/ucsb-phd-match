import json
import re
import urllib.request
from html import unescape
from pathlib import Path

BASE = Path(__file__).resolve().parent
MASTER_JSON = BASE / 'ucsb_professors_master.json'
MASTER_CSV = BASE / 'ucsb_professors_master.csv'
PUBLISH_JSON = BASE / 'ucsb_professor_screening.json'

BAD_CONTENT_BITS = [
    'home people', 'contact address', 'harold frank hall', 'campus affiliations', 'external publications',
    'ucsb publications', 'awards', 'phone', 'personal website', 'education', 'affiliations affiliations',
    'me research areas', 'research areas', 'people faculty'
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
    m = re.search(r'<main[^>]*>(.*?)</main>', html, re.S|re.I)
    if m:
        text = clean_profile_text(m.group(1))
        if len(text) > 200:
            return text
    paras = re.findall(r'<p>(.*?)</p>', html, re.S|re.I)
    cleaned = [clean_profile_text(p) for p in paras]
    cleaned = [p for p in cleaned if len(p) > 40]
    return ' '.join(cleaned[:8]).strip()


def sentence_chunks(text):
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def load_master():
    return json.loads(MASTER_JSON.read_text())


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
        url = rec.get('ucsb_profile_url','').strip()
        if not url:
            continue
        try:
            html = fetch(url)
            text = extract_main_text(html)
            if not text:
                continue
            rec['deep_profile_text'] = text[:4000]
            sentences = sentence_chunks(text)
            if sentences:
                rec['research_summary_long'] = ' '.join(sentences[:3])[:900]
            rec['extraction_notes'] = 'Deep-enriched from individual UCSB profile page plus prior neutral master data.'
            rec['source_quality'] = 'high' if rec.get('email') and rec.get('ucsb_profile_url') and rec.get('research_summary_long') else rec.get('source_quality','medium_high')
        except Exception as e:
            rec['deep_profile_error'] = str(e)
    return master


if __name__ == '__main__':
    master = load_master()
    master = enrich(master)
    save_master(master)
    save_publish(master)
    print('deep enrichment complete')
