# Render deploy notes for UCSB PhD Match backend

## Service type
Use: Web Service

## Repo
GitHub repo: leopahleteg01/ucsb-phd-match

## Runtime
Python 3

## Build command
python -V

## Start command
python render_app.py

## Required environment variables
- OPENCLAW_API_URL = http://YOUR_OPENCLAW_SERVER_IP_OR_HOST:18789/v1/chat/completions
- OPENCLAW_GATEWAY_TOKEN = your gateway token
- OPENCLAW_BACKEND_MODEL = openai-codex/gpt-5.4

## Notes
- This backend expects the OpenClaw gateway HTTP chat endpoint to be enabled.
- If the OpenClaw server is not publicly reachable from Render, this bridge will still fail.
- In that case we would need either:
  - a public proxy path on the OpenClaw host, or
  - move the AI backend to the same reachable environment as OpenClaw.
