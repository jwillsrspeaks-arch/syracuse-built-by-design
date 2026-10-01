# BUILT BY DESIGN — Assessment Tool

## What this is
A single-file, dependency-free assessment app: `index.html` (7 pillars x 10 Likert questions,
local-storage autosave, team roster aggregation, print-ready report). No build step, no backend,
no external credentials.

## Run
`docker compose -f docker-compose.base44.yml up -d` — nginx serves `index.html` on host port 3000.
Edits to index.html are picked up on refresh (Cache-Control: no-cache).

## Verify
`curl -s localhost:3000 | head -3` should return the `<!doctype html>` BUILT BY DESIGN page.

## Quirks
- All state lives in localStorage (`bbd_team_roster_v1`, `bbd_current_draft_v1`).
- Question bank `BBD_BANK` renders wording per lens (athletic/education/corporate/church).
