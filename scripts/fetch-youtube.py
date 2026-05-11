#!/usr/bin/env python3
"""
Fetch live-stream recordings from the Jesus House Kingston YouTube channel.

The channel uses two tabs:
  /videos  — edited uploads (short clips, drama, choir)
  /streams — all live-stream recordings (Sunday Service, Prayer, Bible Study)

This script targets /streams (the live recordings), which is what the website
displays in the sermons archive and watch-live pages.

Usage:
    python3 scripts/fetch-youtube.py                        # all streams
    python3 scripts/fetch-youtube.py --limit 50             # most recent 50
    python3 scripts/fetch-youtube.py --after 20250101       # since Jan 2025
    python3 scripts/fetch-youtube.py --videos               # edited uploads tab
    python3 scripts/fetch-youtube.py --out src/data/videos.json --astro
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CHANNEL_ID   = "UCO1S3nxtFg0_HXEMuZji5zg"
STREAMS_URL  = f"https://www.youtube.com/channel/{CHANNEL_ID}/streams"
VIDEOS_URL   = f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"

# ── Category detection ────────────────────────────────────────────────────────
# Pass 1: title-based (most specific first)
# Pass 2: day-of-week fallback (Sun=6, Mon=0, Wed=2, Fri=4 in Python isoweekday)

TITLE_PATTERNS = [
    ("Monday Morning Prayer",    re.compile(
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
    0: "Monday Morning Prayer",    # Monday
    2: "Wednesday Prayer Meeting", # Wednesday
    4: "Friday Bible Study",       # Friday
    6: "Sunday Service",           # Sunday
}

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

    if result.returncode not in (0, 1):
        print("yt-dlp stderr:", result.stderr[:1000], file=sys.stderr)
        sys.exit(1)

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
        duration    = raw.get("duration")
        view_count  = raw.get("view_count") or 0
        live_status = raw.get("live_status") or ""
        was_live    = live_status in ("was_live", "is_live", "post_live") or bool(raw.get("was_live"))

        # ── Parse date ───────────────────────────────────
        upload_dt: datetime | None = None
        date_iso = date_nice = date_short = ""
        year = month = month_short = ""
        weekday_name = ""

        if upload_str and len(upload_str) == 8:
            try:
                upload_dt   = datetime.strptime(upload_str, "%Y%m%d")
                date_iso    = upload_dt.strftime("%Y-%m-%d")
                date_nice   = upload_dt.strftime("%B %-d, %Y")
                date_short  = upload_dt.strftime("%b %-d, %Y")
                year        = str(upload_dt.year)
                month       = upload_dt.strftime("%B")
                month_short = upload_dt.strftime("%b").upper()
                weekday_name = upload_dt.strftime("%A")
            except ValueError:
                pass

        # ── Duration ─────────────────────────────────────
        dur_str = ""
        if duration:
            h, rem = divmod(int(duration), 3600)
            m, s   = divmod(rem, 60)
            dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        category = categorise(title, upload_dt)

        videos.append({
            "id":           video_id,
            "title":        title,
            "category":     category,
            "date":         date_iso,
            "dateNice":     date_nice,
            "dateShort":    date_short,
            "year":         year,
            "month":        month,
            "monthShort":   month_short,
            "weekday":      weekday_name,
            "duration":     dur_str,
            "views":        view_count,
            "wasLive":      was_live,
            "liveStatus":   live_status,
            "url":          f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail":    f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
        })

    return videos


# ── Reporting ─────────────────────────────────────────────────────────────────

DISPLAY_ORDER = [
    "Sunday Service",
    "Monday Morning Prayer",
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
        "const morningPrayers    = allVideos.filter(v => v.category === 'Monday Morning Prayer');",
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
        description="Fetch Jesus House Kingston YouTube live recordings via yt-dlp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/fetch-youtube.py --limit 20          # quick test
  python3 scripts/fetch-youtube.py --after 20250101    # all of 2025+
  python3 scripts/fetch-youtube.py --astro             # also write .ts file
  python3 scripts/fetch-youtube.py --videos --limit 20 # edited uploads tab
  python3 scripts/fetch-youtube.py --limit 10 --merge  # update with 10 newest
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
        help="Fetch the /videos tab instead of /streams (live recordings)")
    parser.add_argument("--merge",   action="store_true",
        help="Merge fetched videos into existing JSON (safe incremental update)")
    args = parser.parse_args()

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
