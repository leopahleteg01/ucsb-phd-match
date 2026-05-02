import base64
import csv
import io
import json
import os
import re
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from docx import Document
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
CSV_PATH = BASE / 'ucsb_professor_screening.csv'
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

rows = list(csv.DictReader(CSV_PATH.open()))
for r in rows:
    s = (r.get('match_to_your_goal') or '').lower()
    r['_base_fit'] = {
        'extremely close':98,'very close':92,'close on controls':84,'close':82,
        'moderately close':72,'partial match':58,'weak match for robotics':40,
        'weak match for applied robotics':35,'weak for robotics jobs':35,
        'not a fit':10,'needs deeper check':15
    }.get(s, 20)
    blob_parts = [
        r.get('name',''), r.get('department',''), r.get('primary_areas',''),
        r.get('comparison_summary',''), r.get('notes',''), r.get('research_guess',''),
        r.get('title_guess',''), r.get('match_to_your_goal','')
    ]
    r['_blob'] = ' | '.join(blob_parts).lower()

INDEX = b'{"ok":true,"service":"ucsb-phd-match-backend"}'


def heuristic_rank(notes):
    words = [w for w in re.split(r'[^a-z0-9]+', notes.lower()) if len(w) > 2]
    ranked = []
    for r in rows:
        hits = []
        for w in words:
            if w in r['_blob'] and w not in hits:
                hits.append(w)
        ranked.append({
            'name': r['name'],
            'department': r['department'],
            'score': r['_base_fit'] + len(hits) * 3,
            'why': ('Matched on: ' + ', '.join(hits[:10])) if hits else 'Fallback heuristic match from your text.',
            'primary_areas': r.get('primary_areas',''),
            'comparison_summary': r.get('comparison_summary',''),
            'notes': r.get('notes',''),
            'ucsb_profile_url': r.get('ucsb_profile_url',''),
            'website_guess': r.get('website_guess',''),
        })
    ranked.sort(key=lambda x: (-x['score'], x['name']))
    return ranked[:25]


def _extract_account_id_from_jwt(token):
    parts = token.split('.')
    if len(parts) != 3:
        raise RuntimeError('invalid codex token format')
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)).decode())
    account_id = payload.get('https://api.openai.com/auth', {}).get('chatgpt_account_id')
    if not account_id:
        raise RuntimeError('missing chatgpt_account_id in token')
    return account_id


def _build_shortlist():
    shortlist = sorted(rows, key=lambda r: (-r['_base_fit'], r['name']))[:25]
    payload_rows = []
    for r in shortlist:
        payload_rows.append({
            'name': r['name'],
            'department': r['department'],
            'primary_areas': r.get('primary_areas',''),
            'comparison_summary': r.get('comparison_summary',''),
            'notes': r.get('notes',''),
            'ucsb_profile_url': r.get('ucsb_profile_url',''),
            'website_guess': r.get('website_guess',''),
            'base_fit': r['_base_fit'],
        })
    return shortlist, payload_rows


def _merge_scored(shortlist, parsed):
    scored = {x['name']: x for x in parsed.get('results', [])}
    merged = []
    for r in shortlist:
        s = scored.get(r['name'])
        merged.append({
            'name': r['name'],
            'department': r['department'],
            'score': s['score'] if s else r['_base_fit'],
            'why': s['why'] if s else 'Fallback to base fit, no AI explanation returned.',
            'primary_areas': r.get('primary_areas',''),
            'comparison_summary': r.get('comparison_summary',''),
            'notes': r.get('notes',''),
            'ucsb_profile_url': r.get('ucsb_profile_url',''),
            'website_guess': r.get('website_guess',''),
        })
    merged.sort(key=lambda x: (-x['score'], x['name']))
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


def ai_rank_openclaw(notes):
    shortlist, payload_rows = _build_shortlist()
    prompt = (
        'You are ranking UCSB professors for a PhD applicant. '
        'Use the applicant notes and the professor dataset. '
        'Return strict JSON only with this schema: '
        '{"results":[{"name":string,"score":number,"why":string}]}. '
        'Scores should be 0-100 and reflect fit to the applicant notes. '
        'Applicant notes:\n' + notes + '\n\nProfessor data:\n' + json.dumps(payload_rows, ensure_ascii=False)
    )
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
    return _merge_scored(shortlist, parsed)


def ai_rank_direct_codex(notes):
    shortlist, payload_rows = _build_shortlist()
    prompt = (
        'You are ranking UCSB professors for a PhD applicant. '
        'Use the applicant notes and the professor dataset. '
        'Return strict JSON only with this schema: '
        '{"results":[{"name":string,"score":number,"why":string}]}. '
        'Scores should be 0-100 and reflect fit to the applicant notes. '
        'Be decisive and concise. Applicant notes:\n' + notes + '\n\nProfessor data:\n' + json.dumps(payload_rows, ensure_ascii=False)
    )
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
                return _merge_scored(shortlist, parsed)
            elif t in ('response.failed', 'error'):
                raise RuntimeError(json.dumps(evt))
    final_text = ''.join(text_parts)
    if not final_text:
        raise RuntimeError('no codex output received')
    m = re.search(r'\{.*\}', final_text, re.S)
    parsed = json.loads(m.group(0) if m else final_text)
    return _merge_scored(shortlist, parsed)


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
