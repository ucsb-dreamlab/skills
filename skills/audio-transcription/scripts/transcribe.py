#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-genai>=1.65.0",
# ]
# ///
"""
Transcribe audio files with native word-level timestamps and speaker diarization
using the DREAM Lab LiteLLM gateway (`gemini-3.5-transcribe`) and `google-genai`.

Approach:
1. Splits audio longer than 15 minutes into overlapping chunks (default 720s / 12m
   with 60s overlap) using `ffmpeg -c copy` to stay safely below the 15-minute model limit.
2. Calls `client.models.generate_content` with `AudioTranscriptionConfig(word_timestamp=True, ...)`
   against `https://litellm.dreamlab.ucsb.edu` (`/v1beta/models/gemini-3.5-transcribe:generateContent`),
   which returns exact `start_offset` and `end_offset` for every word (and `speaker_label`
   per speaker turn when `diarization=True`) in a single pass.
3. Offsets each chunk's word timestamps by the chunk's start time and stitches adjacent
   chunks across the 60s overlap using `difflib.SequenceMatcher` (splicing at the midpoint
   of the longest matching phrase within the overlap window).
4. Groups the stitched timed words into readable timestamped segments (~30-45s intervals
   at sentence boundaries or speaker changes) and writes `transcript.md`, `transcript.txt`,
   and `transcript.json`.
"""

import argparse
import concurrent.futures
import json
import mimetypes
import os
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from google import genai
from google.genai import types

DEFAULT_BASE_URL = "https://litellm.dreamlab.ucsb.edu"
DEFAULT_MODEL = "gemini-3.5-transcribe"

# Pricing rates for gemini-3.5-transcribe on DREAM Lab LiteLLM:
# $2.00 / 1M audio input tokens ($0.003 / minute at 25 tokens/sec)
# $12.00 / 1M text output tokens
AUDIO_INPUT_COST_PER_TOKEN = 0.000002
OUTPUT_COST_PER_TOKEN = 0.000012


def load_api_key() -> str:
    key = os.environ.get("DREAMLAB_LLM_KEY")
    if key:
        return key
    env_path = Path.home() / ".config" / "dreamlab" / "llm.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "DREAMLAB_LLM_KEY=" in line:
                return line.split("DREAMLAB_LLM_KEY=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "DREAMLAB_LLM_KEY not found in environment or ~/.config/dreamlab/llm.env"
    )


def get_duration(audio_path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]).decode().strip()
    return float(out)


def extract_chunk(audio_path: Path, start: float, duration: float, out_path: Path):
    if out_path.exists() and out_path.stat().st_size > 0:
        return
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(start), "-t", str(duration),
        "-i", str(audio_path), "-c", "copy", str(out_path),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def parse_offset(offset_str: str | None) -> float:
    if not offset_str:
        return 0.0
    s = offset_str.strip()
    if s.endswith("s"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def guess_mime_type(audio_path: Path) -> str:
    ext = audio_path.suffix.lower()
    mime_map = {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".opus": "audio/ogg",
        ".webm": "audio/webm",
    }
    if ext in mime_map:
        return mime_map[ext]
    guessed, _ = mimetypes.guess_type(str(audio_path))
    return guessed or "audio/mp3"


def transcribe_chunk(
    file_path: Path,
    client: genai.Client,
    model: str,
    mime_type: str,
    cache_path: Path,
    diarization: bool = True,
    language_codes: list[str] | None = None,
    custom_vocabulary: list[str] | None = None,
) -> dict:
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            if "parts" in data:
                return data
        except Exception:
            pass

    cfg = types.AudioTranscriptionConfig(
        word_timestamp=True,
        diarization=diarization,
        mode=types.AudioTranscriptionConfigMode.VERBATIM,
        language_codes=language_codes or None,
        custom_vocabulary=custom_vocabulary or None,
    )

    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=file_path.read_bytes(), mime_type=mime_type)
        ],
        config=types.GenerateContentConfig(audio_transcription_config=cfg),
    )

    parts_data = []
    full_text_parts = []
    candidates = resp.candidates or []
    if candidates and candidates[0].content and candidates[0].content.parts:
        for p in candidates[0].content.parts:
            at = p.audio_transcription
            if at is not None:
                words = [
                    {
                        "word": w.word,
                        "start_offset": w.start_offset,
                        "end_offset": w.end_offset,
                    }
                    for w in (at.words or [])
                    if w.word
                ]
                text = (at.text or p.text or "").strip()
                parts_data.append({
                    "text": text,
                    "speaker_label": at.speaker_label,
                    "start_offset": at.start_offset,
                    "end_offset": at.end_offset,
                    "words": words,
                })
                if text:
                    full_text_parts.append(text)
            elif p.text:
                text = p.text.strip()
                parts_data.append({
                    "text": text,
                    "speaker_label": None,
                    "start_offset": None,
                    "end_offset": None,
                    "words": [],
                })
                if text:
                    full_text_parts.append(text)

    usage_meta = resp.usage_metadata
    audio_tokens = 0
    text_prompt_tokens = 0
    if usage_meta and usage_meta.prompt_tokens_details:
        for d in usage_meta.prompt_tokens_details:
            mod = str(getattr(d, "modality", "")).upper()
            if "AUDIO" in mod:
                audio_tokens += d.token_count or 0
            else:
                text_prompt_tokens += d.token_count or 0
    elif usage_meta:
        audio_tokens = usage_meta.prompt_token_count or 0

    output_tokens = (usage_meta.candidates_token_count or 0) if usage_meta else 0
    total_tokens = (usage_meta.total_token_count or 0) if usage_meta else 0

    data = {
        "text": " ".join(full_text_parts),
        "parts": parts_data,
        "usage": {
            "audio_input_tokens": audio_tokens,
            "text_prompt_tokens": text_prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    }
    cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def extract_timed_words(chunk_data: dict, chunk_start: float) -> list[dict]:
    """
    Convert a chunk's parts into a flat list of word dicts with absolute timestamps:
    [{"word": str, "start": float, "end": float, "speaker": str | None}, ...]
    """
    timed_words = []
    for part in chunk_data.get("parts", []):
        speaker = part.get("speaker_label")
        words = part.get("words") or []
        if words:
            for w in words:
                timed_words.append({
                    "word": w["word"],
                    "start": round(chunk_start + parse_offset(w.get("start_offset")), 3),
                    "end": round(chunk_start + parse_offset(w.get("end_offset")), 3),
                    "speaker": speaker,
                })
        elif part.get("text"):
            # Fallback if a part returned text without word list
            raw_words = part["text"].split()
            p_start = chunk_start + parse_offset(part.get("start_offset"))
            p_end = chunk_start + parse_offset(part.get("end_offset"))
            dur = max(0.0, p_end - p_start)
            n = max(1, len(raw_words))
            for i, rw in enumerate(raw_words):
                timed_words.append({
                    "word": rw,
                    "start": round(p_start + (i / n) * dur, 3),
                    "end": round(p_start + ((i + 1) / n) * dur, 3),
                    "speaker": speaker,
                })
    return timed_words


def normalize_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def stitch_timed_words(
    words_a: list[dict],
    words_b: list[dict],
    boundary_start: float,
    overlap: float,
) -> tuple[list[dict], int, int, str]:
    """
    Stitch two overlapping lists of timed word dicts across [boundary_start, boundary_start + overlap].
    Uses exact timestamps to isolate the overlap window, then uses SequenceMatcher
    to splice at the midpoint of the longest matching phrase.
    """
    if not words_a:
        return words_b, 0, 0, ""
    if not words_b:
        return words_a, len(words_a), 0, ""

    window_start = boundary_start - 5.0
    window_end = boundary_start + overlap + 5.0

    # Find indices in words_a that fall in the overlap window (near the tail of words_a)
    tail_indices = [i for i, w in enumerate(words_a) if w["start"] >= window_start]
    if not tail_indices:
        tail_start_idx = max(0, len(words_a) - 220)
    else:
        tail_start_idx = tail_indices[0]

    # Find indices in words_b that fall in the overlap window (near the head of words_b)
    head_indices = [i for i, w in enumerate(words_b) if w["start"] <= window_end]
    if not head_indices:
        head_end_idx = min(len(words_b), 220)
    else:
        head_end_idx = head_indices[-1] + 1

    tail_a = words_a[tail_start_idx:]
    head_b = words_b[:head_end_idx]

    norm_a = [normalize_word(w["word"]) for w in tail_a]
    norm_b = [normalize_word(w["word"]) for w in head_b]

    matcher = SequenceMatcher(None, norm_a, norm_b, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size >= 3]
    if blocks:
        best = max(blocks, key=lambda b: b.size)
        mid = best.size // 2
        keep_a = tail_start_idx + best.a + mid
        skip_b = best.b + mid
    else:
        blocks2 = [b for b in matcher.get_matching_blocks() if b.size >= 2]
        if blocks2:
            best = max(blocks2, key=lambda b: b.size)
            keep_a = tail_start_idx + best.a + 1
            skip_b = best.b + 1
        else:
            # Time-based fallback at the midpoint of the overlap
            mid_time = boundary_start + overlap / 2.0
            keep_a = sum(1 for w in words_a if w["start"] < mid_time)
            skip_b = sum(1 for w in words_b if w["start"] < mid_time)

    preview_words = [
        w["word"] for w in words_b[max(0, skip_b - 5):min(len(words_b), skip_b + 5)]
    ]
    preview = " ".join(preview_words)
    stitched = words_a[:keep_a] + words_b[skip_b:]
    return stitched, keep_a, skip_b, preview


def format_ts(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_specs(total_duration: float, chunk_dur: float, overlap: float, min_tail: float = 15.0):
    step = chunk_dur - overlap
    specs = []
    idx = 0
    start = 0.0
    while start < total_duration:
        dur = min(chunk_dur, total_duration - start)
        if dur < min_tail and specs:
            # Extend the previous chunk slightly if within the 900s limit
            prev_idx, prev_st, prev_dur = specs[-1]
            if (total_duration - prev_st) <= 895.0:
                specs[-1] = (prev_idx, prev_st, total_duration - prev_st)
                break
        specs.append((idx, start, dur))
        if start + dur >= total_duration:
            break
        start += step
        idx += 1
    return specs


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio with native word timestamps and overlapping chunks via DREAM Lab LiteLLM."
    )
    parser.add_argument("audio_file", type=Path, help="Path to input audio file")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("."),
        help="Directory for transcript.md, transcript.txt, and transcript.json (default: .)"
    )
    parser.add_argument(
        "--work-dir", type=Path, default=None,
        help="Directory for chunks/ and cache/ (default: <output-dir>)"
    )
    parser.add_argument(
        "--title", type=str, default=None,
        help="Transcript title for Markdown and JSON headers (default: audio filename stem)"
    )
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument(
        "--chunk-duration", type=float, default=720.0,
        help="Chunk duration in seconds (< 900s model limit, default: 720)"
    )
    parser.add_argument(
        "--overlap", type=float, default=60.0,
        help="Overlap between chunks in seconds (default: 60)"
    )
    parser.add_argument(
        "--segment-interval", type=float, default=30.0,
        help="Target minimum seconds per paragraph segment before breaking at sentence end (default: 30)"
    )
    parser.add_argument(
        "--no-diarization", action="store_true",
        help="Disable speaker diarization"
    )
    parser.add_argument(
        "--include-speakers", action="store_true",
        help="Include speaker labels in Markdown/text output and break segments on speaker changes"
    )
    parser.add_argument(
        "--language", action="append", default=None,
        help="Optional BCP-47 language code hint (e.g. en-US); may be passed multiple times"
    )
    parser.add_argument(
        "--vocab", action="append", default=None,
        help="Optional custom vocabulary phrase to bias recognition; may be passed multiple times"
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Max concurrent transcription requests (default: 4)"
    )
    args = parser.parse_args()

    audio_path = args.audio_file.resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    out_dir = args.output_dir.resolve()
    work_dir = (args.work_dir or out_dir).resolve()
    chunks_dir = work_dir / "chunks"
    cache_dir = work_dir / "cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    ext = audio_path.suffix or ".mp3"
    mime_type = guess_mime_type(audio_path)
    title = args.title or audio_path.stem
    diarization = not args.no_diarization

    api_key = load_api_key()
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            base_url=args.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
        ),
    )

    total_duration = get_duration(audio_path)
    print(f"Total audio duration: {total_duration:.2f}s ({total_duration / 60:.2f} mins)")

    specs = build_specs(total_duration, args.chunk_duration, args.overlap)
    print(
        f"Preparing {len(specs)} overlapping chunk(s) "
        f"({int(args.chunk_duration)}s max each, {int(args.overlap)}s overlap)..."
    )

    tasks = []
    for idx, st, dur in specs:
        cpath = chunks_dir / f"chunk_{idx:02d}_{int(st)}_{int(st + dur)}{ext}"
        jpath = cache_dir / f"chunk_{idx:02d}_{int(st)}_{int(st + dur)}_genai.json"
        extract_chunk(audio_path, st, dur, cpath)
        tasks.append((idx, st, dur, cpath, jpath))

    print(
        f"Transcribing {len(tasks)} chunk(s) via {args.model} "
        f"(word_timestamp=True, diarization={diarization})..."
    )
    results = {}
    total_audio_tokens = 0
    total_output_tokens = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut_map = {
            ex.submit(
                transcribe_chunk,
                cpath,
                client,
                args.model,
                mime_type,
                jpath,
                diarization=diarization,
                language_codes=args.language,
                custom_vocabulary=args.vocab,
            ): (idx, st, dur)
            for idx, st, dur, cpath, jpath in tasks
        }
        done_count = 0
        for fut in concurrent.futures.as_completed(fut_map):
            idx, st, dur = fut_map[fut]
            data = fut.result()
            done_count += 1
            results[idx] = (st, dur, data)
            u = data.get("usage") or {}
            total_audio_tokens += u.get("audio_input_tokens", 0)
            total_output_tokens += u.get("output_tokens", 0)
            w_count = sum(len(p.get("words") or []) for p in data.get("parts", []))
            print(
                f"  [{done_count}/{len(tasks)}] Chunk {idx} "
                f"({format_ts(st)} - {format_ts(st + dur)}): {w_count} timed words"
            )

    # Stitch chunks together using native word timestamps + sequence matching in the overlap
    stitched_words: list[dict] = []
    for idx in sorted(results.keys()):
        st, dur, data = results[idx]
        chunk_words = extract_timed_words(data, st)
        if not stitched_words:
            stitched_words = chunk_words
        else:
            stitched_words, keep_a, skip_b, preview = stitch_timed_words(
                stitched_words, chunk_words, boundary_start=st, overlap=args.overlap
            )
            print(
                f"  Boundary {idx - 1}->{idx} (~{format_ts(st)}): "
                f"kept {keep_a} words, skipped {skip_b} words | splice: '...{preview}...'"
            )

    print(f"Total stitched timed words: {len(stitched_words)}")

    # Group timed words into timestamped paragraphs
    segments = []
    curr_words: list[dict] = []

    for w in stitched_words:
        if curr_words and args.include_speakers and w.get("speaker") != curr_words[-1].get("speaker"):
            seg_start = curr_words[0]["start"]
            seg_end = curr_words[-1]["end"]
            seg_entry = {
                "start": round(seg_start, 2),
                "end": round(seg_end, 2),
                "timestamp": format_ts(seg_start),
                "text": " ".join(x["word"] for x in curr_words),
            }
            if curr_words[0].get("speaker"):
                seg_entry["speaker"] = curr_words[0]["speaker"]
            segments.append(seg_entry)
            curr_words = []

        curr_words.append(w)
        seg_start = curr_words[0]["start"]
        elapsed = w["end"] - seg_start
        word_text = w["word"]
        is_sentence_end = word_text.endswith((".", "?", "!")) or word_text.endswith(('."', '?"', '!"'))

        if (is_sentence_end and elapsed >= args.segment_interval) or elapsed >= (args.segment_interval + 25.0):
            seg_entry = {
                "start": round(seg_start, 2),
                "end": round(w["end"], 2),
                "timestamp": format_ts(seg_start),
                "text": " ".join(x["word"] for x in curr_words),
            }
            if diarization and curr_words[0].get("speaker"):
                seg_entry["speaker"] = curr_words[0]["speaker"]
            segments.append(seg_entry)
            curr_words = []

    if curr_words:
        seg_start = curr_words[0]["start"]
        seg_end = curr_words[-1]["end"]
        seg_entry = {
            "start": round(seg_start, 2),
            "end": round(seg_end, 2),
            "timestamp": format_ts(seg_start),
            "text": " ".join(x["word"] for x in curr_words),
        }
        if diarization and curr_words[0].get("speaker"):
            seg_entry["speaker"] = curr_words[0]["speaker"]
        segments.append(seg_entry)

    full_text = " ".join(w["word"] for w in stitched_words)
    estimated_cost = (
        total_audio_tokens * AUDIO_INPUT_COST_PER_TOKEN
        + total_output_tokens * OUTPUT_COST_PER_TOKEN
    )

    # Write output files
    md_lines = [
        f"# {title}",
        "",
        f"- **Audio File:** `{audio_path.name}`",
        f"- **Duration:** {format_ts(total_duration)} ({total_duration:.1f}s)",
        f"- **Model:** `{args.model}` via DREAM Lab LiteLLM (`{args.base_url}`)",
        "",
        "---",
        "",
    ]
    txt_lines = []

    for seg in segments:
        spk_prefix = f" ({seg['speaker']})" if args.include_speakers and seg.get("speaker") else ""
        md_lines.append(f"**[{seg['timestamp']}]{spk_prefix}** {seg['text']}\n")
        txt_lines.append(f"[{seg['timestamp']}]{spk_prefix} {seg['text']}")

    (out_dir / "transcript.md").write_text("\n".join(md_lines), encoding="utf-8")
    (out_dir / "transcript.txt").write_text("\n\n".join(txt_lines) + "\n", encoding="utf-8")
    (out_dir / "transcript.json").write_text(
        json.dumps({
            "title": title,
            "audio_file": audio_path.name,
            "duration_seconds": total_duration,
            "model": args.model,
            "usage": {
                "audio_input_tokens": total_audio_tokens,
                "output_tokens": total_output_tokens,
                "estimated_cost_usd": round(estimated_cost, 4),
            },
            "segments": segments,
            "words": stitched_words,
            "full_text": full_text,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDone! Generated {len(segments)} timestamped segments ({len(stitched_words)} words).")
    if total_audio_tokens or total_output_tokens:
        print(
            f"Token usage: {total_audio_tokens:,} audio input tokens, "
            f"{total_output_tokens:,} output tokens (estimated cost: ${estimated_cost:.4f})"
        )
    print(f"Saved: {out_dir / 'transcript.md'}, {out_dir / 'transcript.txt'}, {out_dir / 'transcript.json'}")


if __name__ == "__main__":
    main()
