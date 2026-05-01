# Backend step for UCSB PhD Match

## Goal
Connect the live site to a real backend so users can:
- upload PDF / DOC / DOCX / image CVs
- submit notes
- evaluate against the professor dataset
- later use the same model path as OpenClaw / GPT-5.4

## Constraints
- GitHub Pages cannot run server code
- Hostinger/OpenClaw current setup does not yet expose a stable public backend route
- direct browser-to-model is not the right architecture

## Immediate architecture
Frontend:
- GitHub Pages site (already live)

Backend:
- small HTTP service that accepts:
  - notes text
  - files
- extracts text from supported files
- ranks against professor dataset
- returns JSON

## Phase 1 backend
- endpoint: POST /evaluate
- input: multipart or JSON + file upload
- file parsing:
  - txt, md, csv first
  - pdf next
  - image OCR later
- ranking: current heuristic + richer source-backed notes

## Phase 2 backend
- replace heuristic ranker with model-assisted evaluation
- route through same OpenClaw/OpenAI-Codex path where possible

## Main blocker
Need a public backend host or proxy path.
