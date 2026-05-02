import base64
import io
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from docx import Document
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
MASTER_JSON_PATH = BASE / 'ucsb_professors_master.json'
PROFILES_JSON_PATH = BASE / 'ucsb_professor_profiles.json'
HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', '10000'))
OPENCLAW_API_URL = os.environ.get('OPENCLAW_API_URL', '').strip()
OPENCLAW_GATEWAY_TOKEN = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '').strip()
OPENCLAW_BACKEND_MODEL = os.environ.get('OPENCLAW_BACKEND_MODEL', 'openai-codex/gpt-5.4').strip()
PUBLIC_BACKEND_MODE = os.environ.get('PUBLIC_BACKEND_MODE', 'heuristic').strip().lower()
CODEX_ACCESS_TOKEN = os.environ.get('CODEX_ACCESS_TOKEN', '').strip()
CODEX_ACCOUNT_ID = os.environ.get('CODEX_ACCOUNT_ID', '').strip()
CODEX_MODEL = os.environ.get('CODEX_MODEL', 'gpt-5.4').strip()
MAX_FILE_CHARS = 20000
MAX_TOTAL_FILE_CHARS = 50000
AI_CANDIDATE_COUNT = 24

professors = json.loads(MASTER_JSON_PATH.read_text())
professor_profiles = json.loads(PROFILES_JSON_PATH.read_text()) if PROFILES_JSON_PATH.exists() else []
profiles_by_name = {p.get('name',''): p for p in professor_profiles}
for p in professors:
    parts = [
        p.get('name',''), p.get('department',''), p.get('title',''),
        p.get('research_summary_short',''), p.get('research_summary_long',''),
        p.get('research_areas_raw',''), ' '.join(p.get('research_keywords', []) or []),
        p.get('personal_website_url',''), p.get('lab_website_url','')
    ]
    p['_blob'] = ' | '.join(parts).lower()

INDEX = b'{"ok":true,"service":"ucsb-phd-match-backend"}'


def _extract_account_id_from_jwt(token):
    parts = token.split('.')
    if len(parts) != 3:
        raise RuntimeError('invalid codex token format')
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)).decode())
    account_id = payload.get('https://api.openai.com/auth', {}).get('chatgpt_account_id')
    if not account_id:
        raise RuntimeError('missing chatgpt_account_id in token')
    return account_id


def _candidate_pool(notes=''):
    return list(professors)


def _coarse_rank_all(notes):
    words = [w for w in re.split(r'[^a-z0-9]+', notes.lower()) if len(w) > 2]
    lowered = notes.lower()
    phrase_groups = {
        'robotics': ['robotics', 'robot', 'locomotion', 'manipulation'],
        'autonomy': ['autonomy', 'autonomous', 'planning', 'trajectory'],
        'control': ['control', 'controls', 'adaptive control', 'feedback', 'dynamical'],
        'optimization': ['optimization', 'optimal', 'convex'],
        'learning': ['learning', 'machine learning', 'reinforcement learning', 'neural'],
        'simulation': ['simulation', 'simulink', 'matlab', 'modeling', 'models'],
        'digital_twins': ['digital twin', 'digital twins', 'modeling', 'simulation'],
        'systems': ['systems engineering', 'systems', 'cyber-physical', 'dynamics'],
        'physical_ai': ['physical ai', 'robotics', 'autonomy', 'control'],
        'vision': ['vision', 'perception', 'imaging'],
        'vr_ar': ['virtual reality', 'augmented reality', 'vr', 'ar'],
        'security': ['security', 'cybersecurity', 'privacy'],
        'communications': ['communications', 'wireless', 'networking']
    }
    active_groups = [label for label, terms in phrase_groups.items() if any(term in lowered for term in terms)]
    ranked = []
    for p in professors:
        blob = p.get('_blob','')
        hits = []
        for w in words:
            if w in blob and w not in hits:
                hits.append(w)
        methods = p.get('methods_keywords', []) or []
        applications = p.get('application_keywords', []) or []
        research_keywords = p.get('research_keywords', []) or []
        phrase_hits = []
        for label in active_groups:
            if any(term in blob for term in phrase_groups[label]):
                phrase_hits.append(label)
        method_overlap = [w for w in words if any(w in m for m in methods)]
        application_overlap = [w for w in words if any(w in a for a in applications)]
        keyword_overlap = [w for w in words if any(w in k for k in research_keywords)]
        promotion_bonus = 0
        if len(set(method_overlap)) >= 2:
            promotion_bonus += 8
        if len(set(application_overlap)) >= 2:
            promotion_bonus += 8
        if len(set(phrase_hits)) >= 2:
            promotion_bonus += 6
        if 'control' in phrase_hits and 'robotics' in phrase_hits:
            promotion_bonus += 10
        if 'autonomy' in phrase_hits and 'planning' in blob:
            promotion_bonus += 6
        coarse_score = (
            len(hits) * 4
            + len(set(phrase_hits)) * 9
            + len(set(method_overlap)) * 8
            + len(set(application_overlap)) * 8
            + len(set(keyword_overlap)) * 5
            + promotion_bonus
        )
        ranked.append({
            'name': p.get('name',''),
            'department': p.get('department',''),
            'score': coarse_score,
            'why': ('Coarse signals: ' + ', '.join((phrase_hits + hits)[:10])) if (phrase_hits or hits) else 'Low-signal coarse ranking only.',
            'detailed_fit': 'Coarse pass only before deep analysis.',
            'professor_focus': p.get('professor_focus_detailed','') or p.get('research_summary_long','') or p.get('research_summary_short',''),
            'methods_match': ', '.join(methods[:8]),
            'application_match': ', '.join(applications[:8]),
            'strengths_for_you': '',
            'possible_gaps': '',
            'why_not_higher': '',
            'primary_areas': p.get('research_summary_short',''),
            'comparison_summary': p.get('research_summary_long',''),
            'notes': ', '.join(research_keywords[:12]),
            'email': p.get('email',''),
            'ucsb_profile_url': p.get('ucsb_profile_url',''),
            'website_guess': p.get('personal_website_url','') or p.get('lab_website_url',''),
            'google_scholar_url_guess': p.get('google_scholar_url_guess',''),
            '_coarse_hits': hits,
            '_phrase_hits': phrase_hits,
            '_method_overlap': method_overlap,
            '_application_overlap': application_overlap,
            '_keyword_overlap': keyword_overlap,
            '_promotion_bonus': promotion_bonus,
        })
    ranked.sort(key=lambda x: (-x['score'], x['name']))
    return ranked


def _candidate_payload(notes=''):
    coarse_ranked = _coarse_rank_all(notes)
    top_names = {r['name'] for r in coarse_ranked[:AI_CANDIDATE_COUNT]}
    pool = [p for p in professors if p.get('name','') in top_names]
    payload_rows = []
    for p in pool:
        prof = profiles_by_name.get(p.get('name',''), {})
        payload_rows.append({
            'name': p.get('name',''),
            'department': p.get('department',''),
            'affiliations': p.get('affiliations', []),
            'title': p.get('title',''),
            'email': p.get('email',''),
            'research_summary_short': p.get('research_summary_short',''),
            'research_summary_long': p.get('research_summary_long',''),
            'research_areas_raw': p.get('research_areas_raw',''),
            'research_keywords': p.get('research_keywords', []),
            'topic_clusters': p.get('topic_clusters', []),
            'deep_profile_text': p.get('deep_profile_text',''),
            'ucsb_profile_url': p.get('ucsb_profile_url',''),
            'personal_website_url': p.get('personal_website_url',''),
            'lab_website_url': p.get('lab_website_url',''),
            'google_scholar_query': p.get('google_scholar_query',''),
            'google_scholar_url_guess': p.get('google_scholar_url_guess',''),
            'google_query_official': p.get('google_query_official',''),
            'google_query_personal': p.get('google_query_personal',''),
            'google_query_lab': p.get('google_query_lab',''),
            'canonical_profile': prof,
        })
    return pool, payload_rows


def _merge_scored(pool, parsed, coarse_ranked):
    score_map = {x['name']: x for x in parsed.get('results', []) if isinstance(x, dict) and x.get('name')}
    deep_map = {}
    for p in pool:
        s = score_map.get(p['name']) or {}
        ai_why = s.get('why', '') or 'Deep analysis did not return a specific explanation.'
        deep_map[p['name']] = {
            'name': p.get('name',''),
            'department': p.get('department',''),
            'score': s.get('score', 0),
            'why': ai_why,
            'detailed_fit': s.get('detailed_fit', ai_why),
            'professor_focus': s.get('professor_focus', p.get('professor_focus_detailed','') or p.get('research_summary_long','') or p.get('research_summary_short','')),
            'methods_match': s.get('methods_match', ''),
            'application_match': s.get('application_match', ''),
            'strengths_for_you': s.get('strengths_for_you', ''),
            'possible_gaps': s.get('possible_gaps', ''),
            'why_not_higher': s.get('why_not_higher', ''),
            'primary_areas': p.get('research_summary_short',''),
            'comparison_summary': p.get('research_summary_long',''),
            'notes': ', '.join(p.get('research_keywords', [])[:12]),
            'email': p.get('email',''),
            'ucsb_profile_url': p.get('ucsb_profile_url',''),
            'website_guess': p.get('personal_website_url','') or p.get('lab_website_url',''),
            'google_scholar_url_guess': p.get('google_scholar_url_guess',''),
            'analysis_stage': 'deep',
        }
    merged = []
    for item in coarse_ranked:
        if item['name'] in deep_map:
            merged.append(deep_map[item['name']])
    merged.sort(key=lambda x: (-float(x.get('score', 0) or 0), x['name']))
    return merged


def _extract_docx_text(raw_bytes):
    doc = Document(io.BytesIO(raw_bytes))
    return '\n'.join(p.text for p in doc.paragraphs if p.text).strip()


def _extract_pdf_text(raw_bytes):
    reader = PdfReader(io.BytesIO(raw_bytes))
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or '')
        except Exception:
            continue
    return '\n'.join(chunks).strip()


def _extract_text_file(name, raw_bytes):
    lower = (name or '').lower()
    if lower.endswith(('.txt', '.md', '.csv')):
        return raw_bytes.decode('utf-8', 'ignore').strip()
    if lower.endswith('.pdf'):
        return _extract_pdf_text(raw_bytes)
    if lower.endswith('.docx'):
        return _extract_docx_text(raw_bytes)
    if lower.endswith('.doc'):
        raise RuntimeError('legacy .doc is not supported yet, please export as .docx or PDF')
    raise RuntimeError('unsupported file type')


def _collect_uploaded_text(payload):
    files = payload.get('files') or []
    if not isinstance(files, list):
        return '', []
    texts = []
    notices = []
    total = 0
    for f in files:
        if not isinstance(f, dict):
            continue
        name = f.get('name') or 'file'
        content_b64 = f.get('content_base64') or ''
        if not content_b64:
            continue
        try:
            raw_bytes = base64.b64decode(content_b64)
            text = _extract_text_file(name, raw_bytes)
            if not text:
                notices.append(f'{name}: no extractable text found')
                continue
            text = text[:MAX_FILE_CHARS]
            remaining = MAX_TOTAL_FILE_CHARS - total
            if remaining <= 0:
                notices.append(f'{name}: skipped because total upload text limit was reached')
                continue
            text = text[:remaining]
            total += len(text)
            texts.append(f'\n\n[File: {name}]\n{text}')
        except Exception as e:
            notices.append(f'{name}: {e}')
    return ''.join(texts).strip(), notices


def heuristic_rank(notes):
    ranked = _coarse_rank_all(notes)[:AI_CANDIDATE_COUNT]
    for item in ranked:
        item['detailed_fit'] = item.get('why','') + ' This fallback mode uses only a coarse structured ranking, not deep AI analysis.'
        item['analysis_stage'] = 'coarse'
        item['why_not_higher'] = item.get('why_not_higher','') or 'Browser/backend fallback mode did not run the deep analysis stage.'
    return ranked


def _prompt_for_notes(notes, payload_rows):
    return (
        'You are evaluating UCSB professors for a user based only on the current user input and the professor information provided. '
        'Do not use any hidden prior ranking or base score. Generate scores fresh for this run. '
        'Compare all provided professors for this run and rank them relative to the user input. '
        'Return strict JSON only with this schema: '
        '{"results":[{"name":string,"score":number,"why":string,"detailed_fit":string,"professor_focus":string,"methods_match":string,"application_match":string,"strengths_for_you":string,"possible_gaps":string,"why_not_higher":string}]}. '
        'Return results only for the provided top candidates in this deep-analysis stage. '
        'Scores should be 0-100, relative to the current user input only. '
        'Be willing to give low scores when fit is weak. '
        'The field professor_focus should explain clearly what the professor actually works on. '
        'The field detailed_fit should explain in more detail why that professor could fit or not fit the user. '
        'The field methods_match should describe method-level overlap, such as control, optimization, learning, simulation, or systems work. '
        'The field application_match should describe domain overlap, such as robotics, autonomy, VR/AR, cybersecurity, communications, or other application areas. '
        'The field strengths_for_you should say what makes the match compelling. '
        'The field possible_gaps should say what may be missing or less aligned. '
        'The field why_not_higher should explain the main reason the score is not even higher when relevant. '
        'User input:\n' + notes + '\n\nProfessor data:\n' + json.dumps(payload_rows, ensure_ascii=False)
    )


def ai_rank_openclaw(notes):
    coarse_ranked = _coarse_rank_all(notes)
    pool, payload_rows = _candidate_payload(notes)
    prompt = _prompt_for_notes(notes, payload_rows)
    body = json.dumps({
        'model': 'openclaw/default',
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
    }).encode('utf-8')
    req = Request(OPENCLAW_API_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + OPENCLAW_GATEWAY_TOKEN,
        'x-openclaw-model': OPENCLAW_BACKEND_MODEL,
    })
    with urlopen(req, timeout=120) as resp:
        raw = resp.read().decode('utf-8', 'ignore')
    outer = json.loads(raw)
    text = outer['choices'][0]['message']['content']
    m = re.search(r'\{.*\}', text, re.S)
    parsed = json.loads(m.group(0) if m else text)
    return _merge_scored(pool, parsed, coarse_ranked)


def ai_rank_direct_codex(notes):
    coarse_ranked = _coarse_rank_all(notes)
    pool, payload_rows = _candidate_payload(notes)
    prompt = _prompt_for_notes(notes, payload_rows)
    access = CODEX_ACCESS_TOKEN
    if not access:
        raise RuntimeError('missing CODEX_ACCESS_TOKEN')
    account_id = CODEX_ACCOUNT_ID or _extract_account_id_from_jwt(access)
    body = json.dumps({
        'model': CODEX_MODEL,
        'store': False,
        'stream': True,
        'instructions': 'Return only strict JSON. No markdown fences. No extra commentary.',
        'input': [
            {
                'role': 'user',
                'content': [
                    {'type': 'input_text', 'text': prompt}
                ]
            }
        ],
        'text': {'verbosity': 'low'},
        'include': ['reasoning.encrypted_content']
    }).encode('utf-8')
    req = Request('https://chatgpt.com/backend-api/codex/responses', data=body, headers={
        'Authorization': f'Bearer {access}',
        'chatgpt-account-id': account_id,
        'originator': 'pi',
        'OpenAI-Beta': 'responses=experimental',
        'accept': 'text/event-stream',
        'content-type': 'application/json',
        'User-Agent': 'pi (render backend)'
    }, method='POST')
    text_parts = []
    with urlopen(req, timeout=180) as resp:
        for raw_line in resp:
            line = raw_line.decode('utf-8', 'ignore').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if not data or data == '[DONE]':
                continue
            evt = json.loads(data)
            t = evt.get('type', '')
            if t == 'response.output_text.delta':
                text_parts.append(evt.get('delta', ''))
            elif t == 'response.output_text.done' and evt.get('text'):
                final_text = ''.join(text_parts) or evt.get('text', '')
                m = re.search(r'\{.*\}', final_text, re.S)
                parsed = json.loads(m.group(0) if m else final_text)
                return _merge_scored(pool, parsed, coarse_ranked)
            elif t in ('response.failed', 'error'):
                raise RuntimeError(json.dumps(evt))
    final_text = ''.join(text_parts)
    if not final_text:
        raise RuntimeError('no codex output received')
    m = re.search(r'\{.*\}', final_text, re.S)
    parsed = json.loads(m.group(0) if m else final_text)
    return _merge_scored(pool, parsed, coarse_ranked)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, ctype='application/json; charset=utf-8', body=b''):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, body=b'')

    def do_GET(self):
        if self.path == '/' or self.path == '/health':
            self._send(200, body=INDEX)
            return
        self._send(404, body=b'{"error":"not found"}')

    def do_POST(self):
        if self.path != '/evaluate':
            self._send(404, body=b'{"error":"not found"}')
            return
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode('utf-8'))
        except Exception:
            payload = {}
        notes = payload.get('notes', '') or ''
        file_text, file_notices = _collect_uploaded_text(payload)
        combined_notes = notes.strip()
        if file_text:
            combined_notes = (combined_notes + '\n\n' + file_text).strip()
        if not combined_notes.strip():
            self._send(400, body=b'{"error":"notes or supported files required"}')
            return
        mode = 'heuristic'
        results = heuristic_rank(combined_notes)
        if PUBLIC_BACKEND_MODE == 'ai':
            try:
                if CODEX_ACCESS_TOKEN:
                    results = ai_rank_direct_codex(combined_notes)
                    mode = 'ai-direct-codex'
                elif OPENCLAW_API_URL and OPENCLAW_GATEWAY_TOKEN:
                    results = ai_rank_openclaw(combined_notes)
                    mode = 'ai-openclaw'
            except Exception:
                mode = 'heuristic'
                results = heuristic_rank(combined_notes)
        body = json.dumps({'results': results, 'mode': mode, 'file_notices': file_notices}, ensure_ascii=False).encode('utf-8')
        self._send(200, body=body)


if __name__ == '__main__':
    HTTPServer((HOST, PORT), Handler).serve_forever()
