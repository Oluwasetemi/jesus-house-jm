# Jesus House Jamaica — Website

Official website for Jesus House Jamaica (RCCG Kingston), built with [Astro](https://astro.build).

**Live site:** https://www.jesushousejamaica.org

## Stack

- **Framework:** Astro 5 (static output)
- **Styling:** Scoped CSS with design tokens (navy / gold / coral)
- **Animations:** Three.js particle canvas, CSS keyframes
- **Data:** YouTube live recordings fetched via yt-dlp → `src/data/videos.json`

## Development

```sh
npm install
npm run dev        # localhost:4321
npm run build      # production build → dist/
npm run preview    # preview production build
```

## YouTube Data

The sermon archive is powered by `src/data/videos.json` (501+ recordings).
To update it manually:

```sh
# Fetch the 15 most recent streams and merge into existing data
python3 scripts/fetch-youtube.py --limit 15 --merge

# Full re-fetch (takes several minutes)
python3 scripts/fetch-youtube.py
```

The GitHub Action (`.github/workflows/fetch-videos.yml`) runs this automatically
after each service day (Sunday, Monday, Wednesday) and commits the updated JSON.

## Project Structure

```
src/
  components/     nav, footer, Three.js animation
  data/           videos.json (YouTube archive)
  layouts/        Layout.astro (SEO, OG, JSON-LD)
  lib/            church.ts (shared church metadata)
  pages/          19 pages
public/
  favicon.ico / favicon.png / apple-touch-icon.png / og-image.png
scripts/
  fetch-youtube.py
.github/
  workflows/fetch-videos.yml
```
