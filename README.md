# PuzzleVerse - Competitive Jigsaw Creator

PuzzleVerse is a GitHub Pages-ready HTML5 prototype for a jigsaw puzzle game with curated adventure levels, trivia checkpoints, coins, custom image upload puzzles, local world portal, profile, hints, zoom, snapping, and per-puzzle leaderboard logic.

## Current Build

This prototype includes:

- Landscape-style puzzle console
- Side tray for pieces
- Drag and snap puzzle placement
- Zoom controls
- Hint preview system with 10 free hints and paid extra hints
- Adventure Mode with generated 500-level progression logic
- Curated starter levels with trivia at 25%, 50%, and 75%
- Coin economy
- Custom image puzzle creator
- Custom puzzle slots: 10 active puzzles
- Public World Portal using localStorage
- Creator unlock logic and 10% commission design note
- Local profile and leaderboard records
- Seasonal events preview

## How to Run Locally

Open `index.html` directly in a browser, or run:

```bash
python3 -m http.server 8080
```

Then visit:

```text
http://localhost:8080
```

## GitHub Pages Upload

1. Create a GitHub repository.
2. Upload all files from this folder.
3. Go to Repository Settings → Pages.
4. Choose the main branch and root folder.
5. Open the generated GitHub Pages URL.

## Important Production Notes

### Server Needed

The current build uses `localStorage` to simulate persistence. Production should use Firebase, Supabase, PlayFab, or a custom backend for:

- Accounts
- Coin wallet validation
- Custom image storage
- Image moderation
- Puzzle publishing
- Leaderboards
- Anti-cheat validation
- Reports and bans
- Creator commissions
- Friend sharing
- Chat
- Seasonal tournaments

### AI Moderation Needed

The prototype only blocks invalid/oversized local uploads. Production must integrate server-side AI image recognition to block:

- Nudity and sexual content
- Graphic violence
- Hate symbols
- Child exploitation
- Private IDs/documents
- Copyright-problematic public uploads

### Asset Licensing

Starter levels reference images from Wikimedia Commons and NASA-style public sources. Before commercial release, mirror approved files to your own CDN and maintain attribution/license records.

## Suggested Next Milestone

Convert this web prototype into a production-ready app using one of these paths:

1. **Fastest mobile route:** Capacitor wrapper + Firebase backend.
2. **Best game-feel route:** Unity rebuild using this prototype as the design reference.
3. **Most scalable web route:** React/Vite frontend + Supabase backend.


## Educational 500-Image Content Pack

This version adds a 500-record educational puzzle library with local folders, metadata, trivia, placeholder art, source-search URLs, and an optional importer script for Wikimedia/NASA-style open-media sourcing. See `CONTENT_PACK.md`.
