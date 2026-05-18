# Sermons Semantic Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a BM25 full-text search bar to the sermons page that searches across video titles, descriptions, and categories; typing switches to search results mode, clearing restores the month view.

**Architecture:** Orama index is built at Astro build time from `videos.json` (enriched with YouTube descriptions), serialized to a JSON string, and injected into the page via `window.__ORAMA_INDEX__`. A module client script restores the index and runs searches client-side — zero network requests at runtime.

**Tech Stack:** `@orama/orama@3.1.18`, `@orama/plugin-data-persistence@3.1.18`, Astro 5, Python 3 (fetch script), YouTube Data API v3

---

## File Map

| File | Role |
|---|---|
| `scripts/fetch-youtube.py` | Add `description` field to `_make_entry()` + both fetch paths |
| `src/data/videos.json` | Backfilled with `description` field (data task) |
| `src/pages/sermons.astro` | Build Orama index in frontmatter; add search bar + results panel HTML + styles + client script |
| `package.json` | Already has `@orama/orama` + `@orama/plugin-data-persistence` — no change needed |

---

## Task 1: Add `description` to the fetch script

**Files:**
- Modify: `scripts/fetch-youtube.py`

- [ ] **Step 1: Update `_make_entry()` signature to accept `description`**

In `scripts/fetch-youtube.py`, change the function signature at line 110 and the returned dict:

```python
def _make_entry(video_id: str, title: str, upload_dt: datetime | None,
                duration_secs: int | None, view_count: int,
                was_live: bool, live_status: str,
                description: str = "") -> dict:
    """Build the standard videos.json entry dict from parsed fields."""
    date_iso = date_nice = date_short = ""
    year = month = month_short = weekday_name = ""

    if upload_dt:
        date_iso     = upload_dt.strftime("%Y-%m-%d")
        date_nice    = upload_dt.strftime("%B %-d, %Y")
        date_short   = upload_dt.strftime("%b %-d, %Y")
        year         = str(upload_dt.year)
        month        = upload_dt.strftime("%B")
        month_short  = upload_dt.strftime("%b").upper()
        weekday_name = upload_dt.strftime("%A")

    dur_str = ""
    if duration_secs is not None:
        h, rem = divmod(int(duration_secs), 3600)
        m, s   = divmod(rem, 60)
        dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    category = categorise(title, upload_dt)

    return {
        "id":          video_id,
        "title":       title,
        "description": description[:600],
        "category":    category,
        "date":        date_iso,
        "dateNice":    date_nice,
        "dateShort":   date_short,
        "year":        year,
        "month":       month,
        "monthShort":  month_short,
        "weekday":     weekday_name,
        "duration":    dur_str,
        "views":       view_count,
        "wasLive":     was_live,
        "liveStatus":  live_status,
        "url":         f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail":   f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }
```

- [ ] **Step 2: Pass description in the YouTube Data API path**

Find the `videos.append(_make_entry(...))` call inside `fetch_videos_api` (around line 260). Add `description` extraction and pass it:

```python
            title      = snippet.get("title", "").strip()
            raw_desc   = snippet.get("description", "")
            view_count = int(stats.get("viewCount") or 0)
            was_live   = bool(live_det)
            live_stat  = "was_live" if was_live else "not_live"

            # Duration: ISO 8601 → seconds
            duration_secs = _iso8601_to_seconds(content.get("duration", ""))

            # Date: title date > actualStartTime > publishedAt
            upload_dt = parse_title_date(title)

            if upload_dt is None:
                start_str = live_det.get("actualStartTime") or snippet.get("publishedAt", "")
                if start_str:
                    try:
                        upload_dt = datetime.strptime(start_str[:10], "%Y-%m-%d")
                    except ValueError:
                        pass

            if after_dt and upload_dt and upload_dt < after_dt:
                continue

            videos.append(_make_entry(
                vid_id, title, upload_dt, duration_secs,
                view_count, was_live, live_stat,
                description=raw_desc,
            ))
```

- [ ] **Step 3: Pass description in the yt-dlp path**

Find the `videos.append(_make_entry(...))` call inside `fetch_videos` (around line 340). Extract description and pass it:

```python
        duration_secs = int(duration) if duration else None
        raw_desc = (raw.get("description") or "")
        videos.append(_make_entry(video_id, title, upload_dt, duration_secs,
                                  view_count, was_live, live_status,
                                  description=raw_desc))
```

- [ ] **Step 4: Smoke-test the script locally**

```bash
python3 scripts/fetch-youtube.py --limit 2 2>&1 | head -5
python3 -c "
import json
data = json.load(open('src/data/videos.json'))
v = data[0]
print('description field present:', 'description' in v)
print('description length:', len(v.get('description', '')))
print('sample:', v.get('description', '')[:120])
"
```

Expected: `description field present: True` with a non-empty value for recently-fetched videos. Older entries will show empty string until backfilled.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch-youtube.py
git commit -m "feat: add description field to fetch script (both API and yt-dlp paths)"
```

---

## Task 2: Backfill videos.json with descriptions

**Files:**
- Modify: `src/data/videos.json` (data task — run script, don't hand-edit)

> **Prerequisite:** `YOUTUBE_API_KEY` must be set (either in env or passed via `--api-key`).

- [ ] **Step 1: Run full API fetch to populate all descriptions**

```bash
YOUTUBE_API_KEY=<your-key> python3 scripts/fetch-youtube.py \
  --out src/data/videos.json \
  2>&1 | tail -20
```

This re-fetches all videos from the API (no `--limit`, no `--merge`), writing descriptions for all 500+ entries. Takes ~2 minutes (quota: ~11 `search.list` pages × 100 units + ~11 `videos.list` batches × 1 unit ≈ 1110 units of your 10,000 daily allowance).

- [ ] **Step 2: Verify descriptions are present**

```bash
python3 -c "
import json
data = json.load(open('src/data/videos.json'))
with_desc = sum(1 for v in data if v.get('description'))
print(f'{with_desc}/{len(data)} entries have descriptions')
print('Sample:', data[0].get('description', '')[:150])
"
```

Expected: all or nearly all entries have descriptions.

- [ ] **Step 3: Commit**

```bash
git add src/data/videos.json
git commit -m "data: backfill YouTube descriptions into videos.json"
```

---

## Task 3: Build Orama index in sermons.astro frontmatter

**Files:**
- Modify: `src/pages/sermons.astro`

- [ ] **Step 1: Add Orama imports and build the index in the frontmatter**

At the top of the frontmatter (`---` block), add after the existing imports:

```ts
import { create, insert } from '@orama/orama'
import { persist } from '@orama/plugin-data-persistence'

// Build search index at compile time
const searchDb = await create({
  schema: {
    id:          'string',
    title:       'string',
    description: 'string',
    category:    'enum',    // 'enum' enables where: { category: { eq: '...' } } filtering
    date:        'string',
    dateShort:   'string',
    duration:    'string',
    views:       'number',
    url:         'string',
    thumbnail:   'string',
    weekday:     'string',
  } as const,
})

for (const v of allVideos) {
  await insert(searchDb, {
    id:          v.id,
    title:       v.title,
    description: (v as any).description ?? '',
    category:    v.category,
    date:        v.date,
    dateShort:   v.dateShort,
    duration:    v.duration,
    views:       v.views,
    url:         v.url,
    thumbnail:   v.thumbnail,
    weekday:     v.weekday,
  })
}

const serializedIndex = await persist(searchDb, 'json') as string
```

- [ ] **Step 2: Inject the serialized index into the page**

At the bottom of the Astro template (just before `<Footer />`), add:

```astro
<script define:vars={{ serializedIndex }}>
  window.__ORAMA_INDEX__ = serializedIndex
</script>
```

- [ ] **Step 3: Verify build succeeds**

```bash
bun run build 2>&1 | tail -20
```

Expected: build completes without errors. The `serializedIndex` variable will be large (~1–3 MB) but valid.

- [ ] **Step 4: Commit**

```bash
git add src/pages/sermons.astro package.json bun.lock
git commit -m "feat: build Orama search index at compile time and inject into sermons page"
```

---

## Task 4: Add search bar HTML and styles

**Files:**
- Modify: `src/pages/sermons.astro`

- [ ] **Step 1: Add the search bar markup**

In `sermons.astro`, inside `.archive-section > .container`, place the following **between** the `.archive-header` div and the `.tabs-container` div:

```html
<!-- Search bar -->
<form class="search-form" role="search" aria-label="Search sermons">
  <div class="search-input-wrap">
    <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2" aria-hidden="true">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <input
      id="sermon-search"
      type="search"
      class="search-input"
      placeholder="Search sermons…"
      aria-label="Search sermons by title, topic, or scripture"
      autocomplete="off"
      spellcheck="false"
    />
    <button
      type="button"
      id="search-clear"
      class="search-clear"
      aria-label="Clear search"
      hidden
    >×</button>
  </div>
</form>
```

- [ ] **Step 2: Add CSS for the search bar**

In the `<style>` block, add:

```css
/* ── Search bar ──────────────────────────────────── */
.search-form {
  margin-bottom: 1.75rem;
}

.search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 1rem;
  color: var(--color-muted);
  pointer-events: none;
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  padding: 0.875rem 3rem 0.875rem 2.75rem;
  border: 1.5px solid rgba(13, 27, 62, 0.15);
  border-radius: 0.5rem;
  font-family: var(--font-body);
  font-size: 0.95rem;
  color: var(--color-text);
  background-color: var(--color-white);
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
  appearance: none;
}

.search-input:focus {
  outline: none;
  border-color: var(--color-gold);
  box-shadow: 0 0 0 3px rgba(212, 168, 67, 0.15);
}

.search-input::placeholder {
  color: var(--color-muted);
}

/* hide browser's built-in clear button */
.search-input::-webkit-search-cancel-button { display: none; }

.search-clear {
  position: absolute;
  right: 0.875rem;
  background: none;
  border: none;
  font-size: 1.25rem;
  line-height: 1;
  color: var(--color-muted);
  cursor: pointer;
  padding: 0.25rem 0.375rem;
  border-radius: 0.25rem;
  transition: color var(--transition-base);
}

.search-clear:hover { color: var(--color-navy); }
```

- [ ] **Step 3: Verify the search bar renders**

```bash
bun run build && bun run preview
```

Open `http://localhost:4321/sermons` and confirm the search bar appears between the "Sermon Archive" heading and the month tabs.

- [ ] **Step 4: Commit**

```bash
git add src/pages/sermons.astro
git commit -m "feat: add search bar UI to sermons page"
```

---

## Task 5: Add search results panel HTML and styles

**Files:**
- Modify: `src/pages/sermons.astro`

- [ ] **Step 1: Add the results panel markup**

Immediately after `.search-form` (before `.tabs-container`), add:

```html
<!-- Search results panel (hidden until user types) -->
<div id="search-results-panel" hidden>
  <div class="search-results-header">
    <p id="search-results-count" class="search-results-count" aria-live="polite"></p>
    <div class="search-category-pills" role="group" aria-label="Filter by category">
      <button class="cat-pill cat-pill--active" data-category="">All</button>
      <button class="cat-pill" data-category="Sunday Service">Sunday Service</button>
      <button class="cat-pill" data-category="Wednesday Prayer Meeting">Wednesday Prayer</button>
      <button class="cat-pill" data-category="Good Morning Jesus">Good Morning Jesus</button>
      <button class="cat-pill" data-category="Special Service">Special Service</button>
    </div>
  </div>

  <div id="search-results-list" class="sermon-list search-results-list">
    <!-- populated by client script -->
  </div>

  <p id="search-no-results" class="search-no-results" hidden>
    No sermons found.
    <a href="https://www.youtube.com/@jesushousekingston/streams"
       target="_blank" rel="noopener noreferrer">Browse all on YouTube ↗</a>
  </p>
</div>
```

- [ ] **Step 2: Add CSS for the results panel**

In the `<style>` block, add:

```css
/* ── Search results panel ────────────────────────── */
.search-results-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem 1.5rem;
  margin-bottom: 1.25rem;
}

.search-results-count {
  font-size: 0.85rem;
  color: var(--color-muted);
  font-weight: 500;
  min-width: 12ch;
}

.search-category-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.cat-pill {
  padding: 0.3rem 0.875rem;
  font-family: var(--font-body);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1.5px solid rgba(13, 27, 62, 0.15);
  border-radius: 2rem;
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
  transition: all var(--transition-base);
}

.cat-pill:hover {
  border-color: var(--color-navy);
  color: var(--color-navy);
}

.cat-pill--active {
  background-color: var(--color-navy);
  border-color: var(--color-navy);
  color: var(--color-white);
}

.search-results-list {
  border: 1px solid rgba(13, 27, 62, 0.08);
  border-radius: var(--radius-card);
  overflow: hidden;
}

.search-no-results {
  padding: 2.5rem 0;
  text-align: center;
  color: var(--color-muted);
  font-size: 0.95rem;
}

.search-no-results a {
  color: var(--color-coral);
  font-weight: 600;
  text-decoration: none;
}

.search-no-results a:hover { text-decoration: underline; }
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/sermons.astro
git commit -m "feat: add search results panel HTML and styles"
```

---

## Task 6: Add the client-side search script

**Files:**
- Modify: `src/pages/sermons.astro`

- [ ] **Step 1: Add the module script**

At the bottom of the Astro template (after the `define:vars` script, before `</Layout>`), add:

```astro
<script>
  import { restore } from '@orama/plugin-data-persistence'
  import { search } from '@orama/orama'

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const input        = document.getElementById('sermon-search') as HTMLInputElement
  const clearBtn     = document.getElementById('search-clear') as HTMLButtonElement
  const resultsPanel = document.getElementById('search-results-panel') as HTMLDivElement
  const resultsList  = document.getElementById('search-results-list') as HTMLDivElement
  const resultsCount = document.getElementById('search-results-count') as HTMLParagraphElement
  const noResults    = document.getElementById('search-no-results') as HTMLParagraphElement
  const tabsSection  = document.querySelector('.tabs-container') as HTMLElement
  const archiveGrid  = document.querySelector('.archive-grid') as HTMLElement
  const categoryPills = document.querySelectorAll<HTMLButtonElement>('.cat-pill')

  // ── State ─────────────────────────────────────────────────────────────────
  let db: Awaited<ReturnType<typeof restore>> | null = null
  let activeCategory = ''
  let lastQuery = ''

  // ── Init: restore index ───────────────────────────────────────────────────
  ;(async () => {
    const raw = (window as any).__ORAMA_INDEX__
    if (!raw) return
    db = await restore('json', raw)
  })()

  // ── Helpers ───────────────────────────────────────────────────────────────
  function showMonthView() {
    resultsPanel.hidden = true
    tabsSection.hidden  = false
    archiveGrid.hidden  = false
  }

  function showSearchView() {
    resultsPanel.hidden = false
    tabsSection.hidden  = true
    archiveGrid.hidden  = true
  }

  function renderResults(hits: Array<{ document: Record<string, any> }>, query: string) {
    resultsCount.textContent = `${hits.length} result${hits.length === 1 ? '' : 's'} for "${query}"`
    noResults.hidden = hits.length > 0

    if (hits.length === 0) {
      resultsList.innerHTML = ''
      return
    }

    resultsList.innerHTML = hits.map(({ document: v }) => `
      <div class="sermon-row">
        <div class="sermon-type" aria-label="Video">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
          </svg>
        </div>
        <div class="sermon-row-info">
          <p class="sermon-row-title">${v.title}</p>
          <p class="sermon-row-pastor">
            <span class="sermon-cat-pill">${v.category}</span>
            ${v.dateShort}${v.duration ? ` · ${v.duration}` : ''}
          </p>
        </div>
        <a
          href="${v.url}"
          target="_blank"
          rel="noopener noreferrer"
          class="sermon-row-listen"
          aria-label="Watch ${v.title.replace(/"/g, '&quot;')} on YouTube"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
        </a>
      </div>
    `).join('')
  }

  async function runSearch(query: string) {
    if (!db || !query.trim()) {
      showMonthView()
      return
    }

    showSearchView()

    const searchParams: Parameters<typeof search>[1] = {
      term: query,
      properties: ['title', 'description', 'category'],
      boost: { title: 2 },
      limit: 50,
    }

    if (activeCategory) {
      searchParams.where = { category: { eq: activeCategory } }
    }

    const results = await search(db, searchParams)
    renderResults(results.hits, query)
  }

  // ── Debounce ──────────────────────────────────────────────────────────────
  let debounceTimer: ReturnType<typeof setTimeout>

  input.addEventListener('input', () => {
    const query = input.value.trim()
    lastQuery = query
    clearBtn.hidden = query === ''

    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => runSearch(query), 250)
  })

  // ── Clear button ──────────────────────────────────────────────────────────
  clearBtn.addEventListener('click', () => {
    input.value = ''
    lastQuery = ''
    clearBtn.hidden = true
    showMonthView()
    input.focus()
  })

  // ── Category pills ────────────────────────────────────────────────────────
  categoryPills.forEach(pill => {
    pill.addEventListener('click', () => {
      activeCategory = pill.dataset.category ?? ''
      categoryPills.forEach(p => p.classList.toggle('cat-pill--active', p === pill))
      if (lastQuery) runSearch(lastQuery)
    })
  })
</script>
```

- [ ] **Step 2: Verify search works end-to-end**

```bash
bun run build && bun run preview
```

Open `http://localhost:4321/sermons` and:
1. Type `"Mother's Day"` — should show matching services
2. Type `"healing"` — should show results from descriptions
3. Click a category pill — should filter within results
4. Clear the input — month tabs should reappear
5. Type a nonsense query like `"xyzzy123"` — should show "No sermons found"

- [ ] **Step 3: Final build check**

```bash
bun run build 2>&1 | grep -E "error|warn|Error|Warning" | grep -v "Node.js 20"
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/pages/sermons.astro
git commit -m "feat: wire client-side Orama search with debounce, mode switching, and category filter"
```
