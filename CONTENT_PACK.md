# PuzzleVerse Educational Content Pack

This build includes 500 curated educational puzzle records across:

- World places and monuments
- Famous people
- Science and discovery
- Cloud types and weather
- Star constellations
- Deep-sea creatures
- Corals and reef life
- Small critters
- Animals around the world
- Dinosaurs and extinct animals
- Ancient and extinct civilizations

Each puzzle folder contains:

- `placeholder.svg` - playable temporary art
- `meta.json` - puzzle metadata and trivia
- `README.md` - sourcing notes
- `attribution.md` - final credit/license record to complete after image download

## Why placeholders instead of random copied web images?

Commercial launch needs clean rights. Use Wikimedia Commons, NASA, museum/public-domain libraries, or your own licensed image pack. Random internet images can block app store, Pi app, or investor launch approval.

## Fetching images

Run:

```bash
python tools/fetch_open_images.py --limit 25
```

Review all downloaded attributions before using them publicly.
