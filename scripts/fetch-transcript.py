#!/usr/bin/env python3
"""
Download and parse YouTube auto-captions for a podcast episode into the
transcript YAML format used by src/content/podcast/episode-N.md.
Optionally also downloads the episode audio to public/audio/episode-N.mp3.

Usage:
    python3 scripts/fetch-transcript.py <videoId> [--episode N] [--write] [--audio]

    <videoId>     YouTube video ID (e.g. VnqO4Jj-NZY)
    --episode N   Episode number — used to locate/update the content file
    --write       Write transcript directly into the episode's .md frontmatter
    --audio       Also download audio to public/audio/episode-N.mp3
    --chunk-secs  Seconds per transcript segment (default: 6)
    --lang        Caption language (default: en)

Examples:
    # Preview transcript for episode 1
    python3 scripts/fetch-transcript.py VnqO4Jj-NZY --episode 1

    # Write transcript and download audio for episode 1
    python3 scripts/fetch-transcript.py VnqO4Jj-NZY --episode 1 --write --audio

    # Audio only (no transcript)
    python3 scripts/fetch-transcript.py VnqO4Jj-NZY --episode 1 --audio

Note on diarization:
    YouTube auto-captions don't identify speakers. The `speaker` field will
    be empty in the output. Fill it in manually via the CMS or with a
    diarization tool (e.g. pyannote-audio or whisperx).
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to M:SS or H:MM:SS display string."""
    total_secs = ms // 1000
    h, rem = divmod(total_secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def download_captions(video_id: str, lang: str = "en") -> dict:
    """Download JSON3 auto-captions via yt-dlp and return parsed dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--sub-lang", lang,
            "--sub-format", "json3",
            "--skip-download",
            "--no-warnings",
            "-o", f"{tmpdir}/cap",
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        print(f"▶ Downloading captions for {video_id}…", file=sys.stderr)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr[:1000], file=sys.stderr)
            sys.exit(1)

        cap_files = list(Path(tmpdir).glob(f"cap.{lang}*.json3"))
        if not cap_files:
            # Try en-orig
            cap_files = list(Path(tmpdir).glob("cap.*.json3"))
        if not cap_files:
            print("✗ No caption file found. The video may not have auto-captions.", file=sys.stderr)
            sys.exit(1)

        return json.loads(cap_files[0].read_text())


def parse_transcript(data: dict, chunk_secs: int = 6) -> list[dict]:
    """
    Convert JSON3 caption events into transcript segments.

    Each segment groups words until chunk_secs seconds have elapsed,
    producing one entry with: timestamp, speaker (empty), text.
    """
    chunk_ms = chunk_secs * 1000

    # Collect word-level tokens: (abs_start_ms, word_text)
    # Each event gets a boundary marker so we can insert spaces at event joins.
    words: list[tuple[int, str]] = []
    prev_event_had_words = False
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            prev_event_had_words = False
            continue
        t_start = event.get("tStartMs", 0)
        is_append = bool(event.get("aAppend"))
        first_in_event = True
        for seg in segs:
            text = seg.get("utf8", "")
            offset = seg.get("tOffsetMs", 0)
            # Skip bare newlines
            if not text.strip():
                continue
            # Ensure a space at event boundaries when not an append event
            if first_in_event and prev_event_had_words and not is_append:
                if not text.startswith(" "):
                    text = " " + text
            first_in_event = False
            words.append((t_start + offset, text))
        prev_event_had_words = True

    if not words:
        return []

    # Group words into chunks
    segments: list[dict] = []
    chunk_start_ms: int | None = None  # pyright: ignore[reportGeneralTypeIssues]
    chunk_words: list[str] = []

    for abs_ms, word in words:
        if chunk_start_ms is None:
            chunk_start_ms = abs_ms

        # Start a new chunk if we've exceeded chunk_secs
        if abs_ms - chunk_start_ms >= chunk_ms and chunk_words:
            text = _clean(chunk_words)
            if text:
                segments.append({
                    "timestamp": ms_to_timestamp(chunk_start_ms),
                    "speaker": "",
                    "text": text,
                })
            chunk_start_ms = abs_ms
            chunk_words = []

        chunk_words.append(word)

    # Flush last chunk
    if chunk_words and chunk_start_ms is not None:
        text = _clean(chunk_words)
        if text:
            segments.append({
                "timestamp": ms_to_timestamp(chunk_start_ms),
                "speaker": "",
                "text": text,
            })

    return segments


def _clean(words: list[str]) -> str:
    """Join word list and normalise whitespace."""
    joined = "".join(words)
    # Collapse runs of whitespace / newlines
    cleaned = re.sub(r"\s+", " ", joined).strip()
    # Capitalise first letter
    return cleaned[:1].upper() + cleaned[1:] if cleaned else ""


def segments_to_yaml(segments: list[dict]) -> str:
    """Render segments as indented YAML list suitable for frontmatter."""
    lines = ["transcript:"]
    for seg in segments:
        ts = seg["timestamp"]
        sp = seg.get("speaker", "")
        tx = seg["text"].replace('"', '\\"')
        lines.append(f'  - timestamp: "{ts}"')
        lines.append(f'    speaker: "{sp}"')
        lines.append(f'    text: "{tx}"')
    return "\n".join(lines)


def write_to_episode(episode_num: int, segments: list[dict]) -> None:
    """
    Replace (or add) the transcript block in the episode's .md frontmatter.
    Safe: reads the file, replaces only the transcript: block, writes back.
    """
    content_dir = Path("src/content/podcast")
    ep_file = content_dir / f"episode-{episode_num}.md"
    if not ep_file.exists():
        print(f"✗ {ep_file} not found. Create it first.", file=sys.stderr)
        sys.exit(1)

    raw = ep_file.read_text()

    # Split frontmatter from body
    if not raw.startswith("---"):
        print("✗ File does not start with YAML frontmatter (---).", file=sys.stderr)
        sys.exit(1)

    parts = raw.split("---", 2)
    if len(parts) < 3:
        print("✗ Could not parse frontmatter boundaries.", file=sys.stderr)
        sys.exit(1)

    fm_raw = parts[1]  # frontmatter text (without --- delimiters)
    body = parts[2]

    # Strip any existing transcript block
    fm_stripped = re.sub(
        r"\ntranscript:(?:\n  - .*\n    .*\n    .*)*",
        "",
        fm_raw,
    )

    yaml_block = segments_to_yaml(segments)
    new_fm = fm_stripped.rstrip() + "\n" + yaml_block + "\n"
    new_content = f"---{new_fm}---{body}"

    ep_file.write_text(new_content)
    print(f"✓  Wrote {len(segments)} transcript segments → {ep_file}", file=sys.stderr)


def download_audio(video_id: str, episode_num: int) -> None:
    """Download episode audio to public/audio/episode-N.mp3 via yt-dlp."""
    out_dir = Path("public/audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"episode-{episode_num}.mp3"

    if out_path.exists():
        print(f"  Audio already exists: {out_path} ({out_path.stat().st_size // 1024 // 1024}MB)", file=sys.stderr)
        return

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "5",   # ~128 kbps — good for speech
        "--no-warnings",
        "-o", str(out_dir / f"episode-{episode_num}.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    print(f"▶ Downloading audio for episode {episode_num}…", file=sys.stderr)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("✗ Audio download failed.", file=sys.stderr)
        sys.exit(1)
    size_mb = out_path.stat().st_size // 1024 // 1024 if out_path.exists() else "?"
    print(f"✓  Audio → {out_path} ({size_mb}MB)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch YouTube auto-captions and convert to episode transcript YAML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("video_id", help="YouTube video ID")
    parser.add_argument("--episode", type=int, default=None, metavar="N",
        help="Episode number (required with --write or --audio)")
    parser.add_argument("--write", action="store_true",
        help="Write transcript directly into the episode .md file")
    parser.add_argument("--audio", action="store_true",
        help="Download audio to public/audio/episode-N.mp3")
    parser.add_argument("--chunk-secs", type=int, default=6, metavar="N",
        help="Seconds per transcript segment (default: 6)")
    parser.add_argument("--lang", type=str, default="en",
        help="Caption language code (default: en)")
    parser.add_argument("--preview", type=int, default=0, metavar="N",
        help="Print first N segments only (0 = all)")
    args = parser.parse_args()

    if (args.write or args.audio) and args.episode is None:
        parser.error("--write and --audio require --episode N")

    # ── Audio download (independent of transcript) ─────────────────────────────
    if args.audio:
        download_audio(args.video_id, args.episode)
        if not args.write and args.preview == 0:
            return  # audio-only mode: nothing more to do

    # ── Transcript ─────────────────────────────────────────────────────────────
    data = download_captions(args.video_id, args.lang)
    segments = parse_transcript(data, args.chunk_secs)

    if not segments:
        print("✗ No transcript segments generated. Check captions exist.", file=sys.stderr)
        sys.exit(1)

    print(f"✓  {len(segments)} segments parsed", file=sys.stderr)

    if args.write:
        write_to_episode(args.episode, segments)
    else:
        display = segments if not args.preview else segments[:args.preview]
        print(segments_to_yaml(display))
        if args.preview and len(segments) > args.preview:
            print(f"  # … {len(segments) - args.preview} more segments (use --write to save all)")


if __name__ == "__main__":
    main()
