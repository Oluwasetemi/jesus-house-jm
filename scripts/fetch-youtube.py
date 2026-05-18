#!/usr/bin/env python3
"""
Fetch live-stream recordings from the Jesus House Kingston YouTube channel.

The channel uses two tabs:
  /videos  — edited uploads (short clips, drama, choir)
  /streams — all live-stream recordings (Sunday Service, Prayer, Bible Study)

This script targets /streams (the live recordings), which is what the website
displays in the sermons archive and watch-live pages.

Two fetch modes:
  yt-dlp (default) — no API key required; scrapes the channel streams page
  YouTube API      — set YOUTUBE_API_KEY env var or pass --api-key; more
                     reliable, faster, no bot-detection issues

Usage:
    python3 scripts/fetch-youtube.py                        # all streams (yt-dlp)
    python3 scripts/fetch-youtube.py --limit 50             # most recent 50
    python3 scripts/fetch-youtube.py --after 20250101       # since Jan 2025
    python3 scripts/fetch-youtube.py --videos               # edited uploads tab
    python3 scripts/fetch-youtube.py --out src/data/videos.json --astro
    python3 scripts/fetch-youtube.py --api-key AIza...      # use YouTube Data API
    YOUTUBE_API_KEY=AIza... python3 scripts/fetch-youtube.py  # via env var
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

CHANNEL_ID   = "UCO1S3nxtFg0_HXEMuZji5zg"
STREAMS_URL  = f"https://www.youtube.com/channel/{CHANNEL_ID}/streams"
VIDEOS_URL   = f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"

# ── Category detection ────────────────────────────────────────────────────────
# Pass 1: title-based (most specific first)
# Pass 2: day-of-week fallback (Sun=6, Mon=0, Wed=2, Fri=4 in Python isoweekday)

TITLE_PATTERNS = [
    ("Good Morning Jesus",       re.compile(
        r"good\s+morning\s+jesus|monday\s+morning|gmj\b", re.I)),
    ("Wednesday Prayer Meeting", re.compile(
        r"prayer\s+meeting|wednesday\s+prayer|communion\s+service\s+wed"
        r"|wed(\.?\s+)?prayer", re.I)),
    ("Friday Bible Study",       re.compile(
        r"friday\s+bible|bible\s+study\s+friday|friday\s+study", re.I)),
    ("Sunday Service",           re.compile(
        r"sunday\s+service|thanksgiving\s+service|communion\s+service"
        r"|resurrection\s+sunday|special\s+service|sunday\s+worship"
        r"|calling\s+things|break\s+your|think\s+higher|youth\s+sunday"
        r"|collaborations|mother'?s\s+day|father'?s\s+day"
        r"|men'?s\s+(sunday|service)|women'?s\s+(sunday|service)"
        r"|couples\s+(sunday|service)|family\s+sunday", re.I)),
    ("Special Service",          re.compile(
        r"christmas|good\s+friday|praise\s+night|easter|vigil|conference"
        r"|anniversary|concert|choir|drama|crossover|burial|night\s+of\s+worship"
        r"|celebrating\s+the\s+life|wonders\s+of\s+god|faith\s+praise", re.I)),
]

DOW_CATEGORY = {
    0: "Good Morning Jesus",       # Monday
    2: "Wednesday Prayer Meeting", # Wednesday
    4: "Friday Bible Study",       # Friday
    6: "Sunday Service",           # Sunday
}

# Regex to extract a date from a video title, e.g. "May 10, 2026" or "APRIL 27, 2026"
_TITLE_DATE_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(\d{1,2}),?\s+(\d{4})\b",
    re.I,
)

def parse_title_date(title: str) -> datetime | None:
    """Return a datetime parsed from a date string embedded in the title, or None."""
    m = _TITLE_DATE_RE.search(title)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y")
    except ValueError:
        return None

def categorise(title: str, upload_dt: datetime | None) -> str:
    # 1. Try title patterns
    for label, pattern in TITLE_PATTERNS:
        if pattern.search(title):
            return label

    # 2. Fallback: use day of week (0=Mon … 6=Sun)
    if upload_dt:
        dow = upload_dt.weekday()   # 0=Mon, 6=Sun
        if dow in DOW_CATEGORY:
            return DOW_CATEGORY[dow]

    return "Other"


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_entry(video_id: str, title: str, upload_dt: datetime | None,
                duration_secs: int | None, view_count: int,
                was_live: bool, live_status: str) -> dict:
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
        "id":         video_id,
        "title":      title,
        "category":   category,
        "date":       date_iso,
        "dateNice":   date_nice,
        "dateShort":  date_short,
        "year":       year,
        "month":      month,
        "monthShort": month_short,
        "weekday":    weekday_name,
        "duration":   dur_str,
        "views":      view_count,
        "wasLive":    was_live,
        "liveStatus": live_status,
        "url":        f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail":  f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }


def _iso8601_to_seconds(duration: str) -> int | None:
    """Convert ISO 8601 duration (PT1H59M31S) to total seconds."""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return None
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


# ── YouTube Data API v3 fetch ─────────────────────────────────────────────────

YT_API_BASE = "https://www.googleapis.com/youtube/v3"


def _yt_api(endpoint: str, params: dict) -> dict:
    url = f"{YT_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_videos_api(api_key: str, limit: int | None, after: str | None,
                     live_only: bool = True) -> list[dict]:
    """Fetch completed live streams using the YouTube Data API v3.

    Costs: search.list = 100 quota units, videos.list = 1 unit per batch.
    Daily free quota: 10,000 units → up to ~99 search calls per day.
    """
    print(f"▶ Fetching via YouTube Data API (channel: {CHANNEL_ID})", file=sys.stderr)

    # ── 1. Collect video IDs via search.list ──────────────────────────────────
    video_ids: list[str] = []
    page_token: str | None = None
    max_results = min(limit or 50, 50)  # API cap per page is 50

    after_dt = datetime.strptime(after, "%Y%m%d") if after else None

    while True:
        params: dict = {
            "part":       "id",
            "channelId":  CHANNEL_ID,
            "type":       "video",
            "order":      "date",
            "maxResults": max_results,
            "key":        api_key,
        }
        if live_only:
            params["eventType"] = "completed"
        if page_token:
            params["pageToken"] = page_token

        data = _yt_api("search", params)
        for item in data.get("items", []):
            video_ids.append(item["id"]["videoId"])

        page_token = data.get("nextPageToken")
        if not page_token or (limit and len(video_ids) >= limit):
            break

    if limit:
        video_ids = video_ids[:limit]

    if not video_ids:
        print("  No videos found.", file=sys.stderr)
        return []

    print(f"  Found {len(video_ids)} video IDs — fetching details…", file=sys.stderr)

    # ── 2. Fetch full metadata via videos.list (batch in groups of 50) ────────
    videos: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = _yt_api("videos", {
            "part":  "snippet,contentDetails,statistics,liveStreamingDetails",
            "id":    ",".join(batch),
            "key":   api_key,
        })

        for item in data.get("items", []):
            vid_id    = item["id"]
            snippet   = item.get("snippet", {})
            content   = item.get("contentDetails", {})
            stats     = item.get("statistics", {})
            live_det  = item.get("liveStreamingDetails", {})

            title      = snippet.get("title", "").strip()
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
            ))

    return videos


# ── yt-dlp fetch ─────────────────────────────────────────────────────────────

def fetch_videos(url: str, limit: int | None, after: str | None) -> list[dict]:
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-warnings",
        "--sleep-interval", "0.5",
        "--max-sleep-interval", "2",
    ]

    if limit:
        cmd += ["--playlist-end", str(limit)]
    if after:
        cmd += ["--dateafter", after]

    cmd.append(url)

    print(f"▶ Fetching: {url}", file=sys.stderr)
    if limit:
        print(f"  Limit: {limit} videos", file=sys.stderr)
    if after:
        print(f"  After: {after}", file=sys.stderr)
    print("  (may take a minute…)\n", file=sys.stderr)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stderr.strip():
        print("yt-dlp stderr:\n" + result.stderr[:2000], file=sys.stderr)

    if result.returncode not in (0, 1):
        sys.exit(1)

    if not result.stdout.strip():
        print("  ⚠️  yt-dlp returned no output — YouTube may be blocking this IP.", file=sys.stderr)
        print("     Consider setting YOUTUBE_API_KEY to bypass bot detection.", file=sys.stderr)
        return []

    videos = []
    for line in result.stdout.strip().splitlines():
        if not line.startswith("{"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        video_id    = raw.get("id", "")
        title       = (raw.get("title") or "").strip()
        upload_str  = raw.get("upload_date", "")   # "20260503"
        release_ts  = raw.get("release_timestamp")  # epoch int, set for live streams
        duration    = raw.get("duration")
        view_count  = raw.get("view_count") or 0
        live_status = raw.get("live_status") or ""
        was_live    = live_status in ("was_live", "is_live", "post_live") or bool(raw.get("was_live"))

        # Priority: title date > release_timestamp > upload_date (may be +1 day)
        upload_dt = parse_title_date(title)

        if upload_dt is None and release_ts:
            try:
                upload_dt = datetime.utcfromtimestamp(int(release_ts))
            except (ValueError, OSError):
                pass

        if upload_dt is None and upload_str and len(upload_str) == 8:
            try:
                upload_dt = datetime.strptime(upload_str, "%Y%m%d")
            except ValueError:
                pass

        duration_secs = int(duration) if duration else None
        videos.append(_make_entry(video_id, title, upload_dt, duration_secs,
                                  view_count, was_live, live_status))

    return videos


# ── Reporting ─────────────────────────────────────────────────────────────────

DISPLAY_ORDER = [
    "Sunday Service",
    "Good Morning Jesus",
    "Wednesday Prayer Meeting",
    "Friday Bible Study",
    "Special Service",
    "Other",
]

def print_report(videos: list[dict]) -> None:
    by_cat: dict[str, list[dict]] = {}
    for v in videos:
        by_cat.setdefault(v["category"], []).append(v)

    live_total = sum(1 for v in videos if v["wasLive"])
    print(f"\n{'='*72}")
    print(f"  Jesus House Kingston — {len(videos)} videos  ({live_total} live recordings)")
    print(f"{'='*72}")

    for cat in DISPLAY_ORDER:
        items = by_cat.get(cat, [])
        if not items:
            continue
        live_n = sum(1 for v in items if v["wasLive"])
        print(f"\n{'─'*72}")
        print(f"  {cat}  ·  {len(items)} videos  ({live_n} live)")
        print(f"  {'DATE':<18} {'DAY':<10} {'ID':<13} {'DUR':>8}   TITLE")
        print(f"  {'─'*18} {'─'*10} {'─'*13} {'─'*8}   {'─'*44}")
        for v in items:
            flag = "🔴" if v["wasLive"] else "  "
            print(
                f"  {flag} {v['dateShort'] or '?':>16}  "
                f"{v['weekday'][:3] or '':>3}  "
                f"{v['id']:<13}  {v['duration']:>8}   "
                f"{v['title'][:50]}"
            )


# ── Astro/TS snippet ──────────────────────────────────────────────────────────

def emit_astro_snippet(videos: list[dict]) -> str:
    lines = [
        "// Auto-generated by scripts/fetch-youtube.py — do not edit by hand",
        "// Paste into the frontmatter (---) of sermons.astro / watch-live.astro",
        "",
        "const CHANNEL_ID = 'UCO1S3nxtFg0_HXEMuZji5zg';",
        "",
        "const allVideos = [",
    ]
    for v in videos:
        lines.append(
            f"  {{"
            f" id: {json.dumps(v['id'])},"
            f" title: {json.dumps(v['title'])},"
            f" category: {json.dumps(v['category'])},"
            f" date: {json.dumps(v['dateNice'])},"
            f" dateShort: {json.dumps(v['dateShort'])},"
            f" duration: {json.dumps(v['duration'])},"
            f" wasLive: {str(v['wasLive']).lower()},"
            f" thumbnail: {json.dumps(v['thumbnail'])} }},"
        )
    lines += [
        "] as const;",
        "",
        "// Filtered views — use these directly in page templates",
        "const sundayServices    = allVideos.filter(v => v.category === 'Sunday Service');",
        "const morningPrayers    = allVideos.filter(v => v.category === 'Good Morning Jesus');",
        "const wednesdayMeetings = allVideos.filter(v => v.category === 'Wednesday Prayer Meeting');",
        "const fridayStudy       = allVideos.filter(v => v.category === 'Friday Bible Study');",
        "const recentVideos      = allVideos.slice(0, 6);",
    ]
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def merge_videos(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """Merge fresh videos into existing list, deduplicating by id, newest first."""
    by_id = {v["id"]: v for v in existing}
    for v in fresh:
        by_id[v["id"]] = v  # fresh data wins on conflict
    merged = sorted(by_id.values(), key=lambda v: v["date"], reverse=True)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Jesus House Kingston YouTube live recordings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/fetch-youtube.py --limit 20              # yt-dlp, quick test
  python3 scripts/fetch-youtube.py --after 20250101        # all of 2025+
  python3 scripts/fetch-youtube.py --astro                 # also write .ts file
  python3 scripts/fetch-youtube.py --videos --limit 20     # edited uploads tab
  python3 scripts/fetch-youtube.py --limit 10 --merge      # incremental update
  python3 scripts/fetch-youtube.py --api-key AIza... --limit 15  # YouTube API
  YOUTUBE_API_KEY=AIza... python3 scripts/fetch-youtube.py       # via env var
        """,
    )
    parser.add_argument("--limit",   type=int,  default=None, metavar="N",
        help="Fetch only the N most recent videos")
    parser.add_argument("--after",   type=str,  default=None, metavar="YYYYMMDD",
        help="Only include videos uploaded on/after this date")
    parser.add_argument("--out",     type=str,  default="src/data/videos.json",
        help="Output JSON path (default: src/data/videos.json)")
    parser.add_argument("--astro",   action="store_true",
        help="Also write a .ts data file for use in Astro pages")
    parser.add_argument("--videos",  action="store_true",
        help="Fetch the /videos tab instead of /streams (yt-dlp mode only)")
    parser.add_argument("--merge",   action="store_true",
        help="Merge fetched videos into existing JSON (safe incremental update)")
    parser.add_argument("--api-key", type=str,  default=None, metavar="KEY",
        help="YouTube Data API v3 key (overrides YOUTUBE_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("YOUTUBE_API_KEY")

    if api_key:
        fresh = fetch_videos_api(api_key, args.limit, args.after)
    else:
        url = VIDEOS_URL if args.videos else STREAMS_URL
        fresh = fetch_videos(url, args.limit, args.after)

    # ── Merge with existing data if requested ─────────────
    if args.merge:
        out_path = Path(args.out)
        existing: list[dict] = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text())
                print(f"  Merging {len(fresh)} fresh into {len(existing)} existing…", file=sys.stderr)
            except json.JSONDecodeError:
                pass
        videos = merge_videos(existing, fresh)
    else:
        videos = fresh

    print_report(videos)

    # ── JSON ──────────────────────────────────────────────
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(videos, indent=2, ensure_ascii=False))
    print(f"\n✓  JSON  → {out_path}  ({len(videos)} entries)")

    # ── Astro TS snippet ──────────────────────────────────
    if args.astro:
        ts_path = out_path.with_suffix(".ts")
        ts_path.write_text(emit_astro_snippet(videos))
        print(f"✓  TS    → {ts_path}")

    # ── Summary table ─────────────────────────────────────
    cats: dict[str, int] = {}
    for v in videos:
        cats[v["category"]] = cats.get(v["category"], 0) + 1
    print("\nCategory breakdown:")
    for cat in DISPLAY_ORDER:
        n = cats.get(cat, 0)
        if n:
            bar = "█" * min(n, 40)
            print(f"  {n:>4}  {cat:<28}  {bar}")


if __name__ == "__main__":
    main()
