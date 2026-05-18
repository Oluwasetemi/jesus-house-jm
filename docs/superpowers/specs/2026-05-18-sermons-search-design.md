# Sermons Semantic Search — Design Spec

**Date:** 2026-05-18
**Status:** Approved

---

## Problem

The sermons page shows only the 8 most recent months of videos with no way to search across the full 506-video archive. Users cannot find sermons by topic, scripture reference, or keyword.

## Goal

Add a search bar above the month tabs that supports both keyword and meaning-based queries (e.g. `"Mother's Day"`, `"Acts 2"`, `"sermons about healing"`). Typing switches to search results mode; clearing restores the month view.

---

## Data Layer

### Add `description` to `videos.json`

Every entry gains a `description` field (max 600 characters, truncated at write time):

```json
{
  "id": "mfC83gpopV4",
  "title": "Sunday Service | Jesus House Kingston | May 17, 2026",
  "description": "Join us for Sunday Service at Jesus House Kingston...",
  "category": "Sunday Service",
  "date": "2026-05-17",
  ...
}
```

### Fetch script changes (`scripts/fetch-youtube.py`)

- `_make_entry()` gains a `description: str = ""` parameter and writes it to the entry dict
- **YouTube Data API path** (`fetch_videos_api`): `snippet.description` is already present in the `videos.list` response — pass first 600 chars to `_make_entry()`
- **yt-dlp path** (`fetch_videos`): `raw.get("description", "")` is available in yt-dlp JSON output — pass first 600 chars to `_make_entry()`

### One-time backfill

Run with the YouTube Data API to populate descriptions for all existing entries:

```bash
YOUTUBE_API_KEY=<key> python3 scripts/fetch-youtube.py --out src/data/videos.json
```

Future incremental cron runs (`--limit 15 --merge`) will include descriptions for new videos automatically.

---

## Index Architecture

### Library

- `@orama/orama` — BM25 full-text search, runs entirely client-side
- `@orama/plugin-data-persistence` — serialize/restore index as JSON

### Build-time (Astro frontmatter)

The Orama index is built once during `astro build`, serialized to a JSON string, and injected into the page as an inline `<script>` variable. No separate build step, no extra static file, zero network request at runtime.

```ts
import { create, insert } from '@orama/orama'
import { persistToJSON } from '@orama/plugin-data-persistence'

const db = await create({
  schema: { id: 'string', title: 'string', description: 'string', category: 'string', date: 'string' }
})
for (const v of allVideos) {
  await insert(db, { id: v.id, title: v.title, description: v.description ?? '', category: v.category, date: v.date })
}
const serializedIndex = await persistToJSON(db)
```

### Client-side search call

```ts
const db = await restoreFromJSON(serializedIndex)
const results = await search(db, {
  term: query,
  properties: ['title', 'description', 'category'],
  boost: { title: 2 },
  limit: 20,
})
```

Title is boosted 2× so exact title matches rank above description matches.

---

## UI & Behaviour

### Search bar

Placed between the "Sermon Archive" heading and the month tabs. Contains:
- Search icon (left)
- Text input (`placeholder="Search sermons…"`)
- Clear (`×`) button — visible only when input is non-empty

### Mode switching

| State | What's visible |
|---|---|
| Input empty | Month tabs + archive grid (current layout, unchanged) |
| Input non-empty | Month tabs + archive grid hidden; search results panel shown |
| Clear / backspace to empty | Month view restored instantly |

### Search results panel

- Result count above list: `12 results for "healing"`
- Category filter pills: `All · Sunday Service · Wednesday Prayer Meeting · Good Morning Jesus · Special Service` — narrow within current search query; pill labels match the exact `category` values in `videos.json`
- Results use the existing `sermon-row` style (icon, title, category pill, date, play button)
- Sorted by BM25 relevance score, not by date
- Zero results: `"No sermons found for '...'"` + link to YouTube channel

### Debounce

250ms after last keystroke before search fires.

### Accessibility

- `role="search"` on the search form
- `aria-live="polite"` on the results container (screen readers announce result count)
- Clear button has `aria-label="Clear search"`

---

## Files Changed

| File | Change |
|---|---|
| `scripts/fetch-youtube.py` | Add `description` to `_make_entry()`, both API and yt-dlp paths |
| `src/data/videos.json` | Re-fetched with descriptions (one-time backfill) |
| `src/pages/sermons.astro` | Build Orama index in frontmatter; add search bar, results panel, client script |
| `package.json` | Add `@orama/orama`, `@orama/plugin-data-persistence` |

---

## Out of Scope

- Vector/embedding-based semantic search (not needed given rich descriptions)
- Server-side search API
- Search on any page other than `/sermons`
- Persisting search query in URL
