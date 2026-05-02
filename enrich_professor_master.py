import csv
import json
import re
import urllib.request
from html import unescape
from pathlib import Path

BASE = Path(__file__).resolve().parent
MASTER_JSON = BASE / 'ucsb_professors_master.json'
MASTER_CSV = BASE / 'ucsb_professors_master.csv'
PUBLISH_JSON = BASE / 'ucsb_professor_screening.json'

FACULTY_PAGES = {
    'ME': 'https://me.ucsb.edu/people?tid=All',
    'CS': 'https://cs.ucsb.edu/index.php/people/faculty',
    'ECE': 'https://www.ece.ucsb.edu/people/faculty',
}


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


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def load_master():
    return json.loads(MASTER_JSON.read_text())


def save_master(master):
    MASTER_JSON.write_text(json.dumps(master, ensure_ascii=False, indent=2))
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
            'google_scholar_query': p.get('google_scholar_query',''),
            'google_query_official': p.get('google_query_official',''),
            'google_query_personal': p.get('google_query_personal',''),
            '_blob': ' | '.join([
                p.get('name',''), p.get('department',''), p.get('title',''), p.get('email',''),
                p.get('research_summary_short',''), p.get('research_summary_long',''),
                ' '.join(p.get('research_keywords', []) or [])
            ]).lower()
        })
    PUBLISH_JSON.write_text(json.dumps(rows, ensure_ascii=False))


def build_cs_map(html):
    entries = {}
    for block in re.findall(r'<div[^>]+class="[^"]*person-card[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.S|re.I):
        text = strip_tags(block)
        hrefs = re.findall(r'href="([^"]+/people/faculty/[^"]+|/index.php/people/faculty/[^"]+)"', block, re.I)
        mail = re.findall(r'mailto:([^"\']+)', block, re.I)
        m = re.search(r'/people/faculty/([^"/]+)', ' '.join(hrefs))
        if not m:
            continue
        slug = m.group(1)
        entries[slug] = {
            'text': text,
            'email': mail[0] if mail else '',
            'url': 'https://cs.ucsb.edu/index.php/people/faculty/' + slug,
        }
    if not entries:
        for slug, email in re.findall(r'/index.php/people/faculty/([^"/]+).*?mailto:([^"\']+)', html, re.S|re.I):
            entries[slug] = {'text': '', 'email': email, 'url': 'https://cs.ucsb.edu/index.php/people/faculty/' + slug}
    return entries


def build_ece_map(html):
    entries = {}
    for slug, email in re.findall(r'/people/faculty/([^"/]+).*?mailto:([^"\']+)', html, re.S|re.I):
        entries[slug] = {'email': email, 'url': 'https://www.ece.ucsb.edu/people/faculty/' + slug}
    return entries


def build_me_emails(html):
    emails = set(re.findall(r'mailto:([^"\']+)', html, re.I))
    return list(sorted(emails))


def enrich_master(master):
    cs_html = fetch(FACULTY_PAGES['CS'])
    ece_html = fetch(FACULTY_PAGES['ECE'])
    me_html = fetch(FACULTY_PAGES['ME'])
    cs_map = build_cs_map(cs_html)
    ece_map = build_ece_map(ece_html)
    me_emails = build_me_emails(me_html)

    for rec in master:
        url = rec.get('ucsb_profile_url','')
        name = rec.get('name','')
        lower_name = name.lower()
        if 'cs.ucsb.edu' in url:
            m = re.search(r'/people/faculty/([^/]+)$', url)
            slug = m.group(1) if m else slugify(name)
            hit = cs_map.get(slug)
            if hit:
                if hit.get('email'):
                    rec['email'] = hit['email']
                rec['ucsb_profile_url'] = hit['url']
                rec['ucsb_profile_source'] = hit['url']
        elif 'ece.ucsb.edu' in url:
            m = re.search(r'/people/faculty/([^/]+)$', url)
            slug = m.group(1) if m else slugify(name)
            hit = ece_map.get(slug)
            if hit:
                if hit.get('email'):
                    rec['email'] = hit['email']
                rec['ucsb_profile_url'] = hit['url']
                rec['ucsb_profile_source'] = hit['url']
        elif 'me.ucsb.edu' in url:
            if not rec.get('email'):
                guesses = [
                    ''.join(ch for ch in lower_name if ch.isalpha()) + '@ucsb.edu',
                    lower_name.split()[0] + '@ucsb.edu' if lower_name.split() else ''
                ]
                for g in guesses:
                    if g in me_emails:
                        rec['email'] = g
                        break
        official_url = rec.get('ucsb_profile_url','')
        website_url = rec.get('personal_website_url','') or rec.get('lab_website_url','')
        rec['website_status'] = 'present' if website_url else 'missing'
        rec['scholar_status'] = 'query_ready'
        rec['website_domain'] = re.sub(r'^https?://([^/]+)/?.*$', r'\1', website_url) if website_url else ''
        rec['ucsb_domain'] = re.sub(r'^https?://([^/]+)/?.*$', r'\1', official_url) if official_url else ''
        if not rec.get('google_query_official'):
            rec['google_query_official'] = f"{name} UCSB official page"
        if not rec.get('google_scholar_query'):
            rec['google_scholar_query'] = f"{name} Google Scholar UCSB"
        if not rec.get('google_query_personal'):
            rec['google_query_personal'] = f"{name} UCSB personal website"
        if not rec.get('google_query_lab'):
            rec['google_query_lab'] = f"{name} UCSB lab website"
        if not rec.get('google_scholar_url_guess'):
            rec['google_scholar_url_guess'] = f"https://scholar.google.com/scholar?q={name.replace(' ', '+')}+UCSB"
        rec['source_quality'] = 'medium_high' if rec.get('email') and rec.get('ucsb_profile_url') else rec.get('source_quality','medium')
    return master


if __name__ == '__main__':
    master = load_master()
    master = enrich_master(master)
    save_master(master)
    save_publish(master)
    print('enriched master and publish artifacts')
