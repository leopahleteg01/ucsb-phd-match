import csv
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent
CSV_PATH = BASE / 'ucsb_professor_screening.csv'
HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', '10000'))
OPENCLAW_API_URL = os.environ.get('OPENCLAW_API_URL', '').strip()
OPENCLAW_GATEWAY_TOKEN = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '').strip()
OPENCLAW_BACKEND_MODEL = os.environ.get('OPENCLAW_BACKEND_MODEL', 'openai-codex/gpt-5.4').strip()

rows = list(csv.DictReader(CSV_PATH.open()))
for r in rows:
    s = (r.get('match_to_your_goal') or '').lower()
    r['_base_fit'] = {
        'extremely close':98,'very close':92,'close on controls':84,'close':82,
        'moderately close':72,'partial match':58,'weak match for robotics':40,
        'weak match for applied robotics':35,'weak for robotics jobs':35,
        'not a fit':10,'needs deeper check':15
    }.get(s, 20)

INDEX = b'{"ok":true,"service":"ucsb-phd-match-backend"}'


def ai_rank(notes):
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
        if not notes.strip():
            self._send(400, body=b'{"error":"notes required"}')
            return
        if not OPENCLAW_API_URL or not OPENCLAW_GATEWAY_TOKEN:
            self._send(500, body=b'{"error":"backend env missing"}')
            return
        try:
            results = ai_rank(notes)
            body = json.dumps({'results': results}, ensure_ascii=False).encode('utf-8')
            self._send(200, body=body)
        except Exception as e:
            body = json.dumps({'error': 'backend evaluation failed', 'detail': str(e)}).encode('utf-8')
            self._send(500, body=body)


if __name__ == '__main__':
    HTTPServer((HOST, PORT), Handler).serve_forever()
