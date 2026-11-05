---
name: audio-transcription
description: Transcribe audio files (including recordings over 15 minutes) with native word-level timestamps and speaker diarization using the DREAM Lab LiteLLM gateway (gemini-3.5-transcribe via google-genai AudioTranscriptionConfig) and ffmpeg overlapping chunks.
---

# Audio Transcription via DREAM Lab LiteLLM Gateway

Use this skill to transcribe audio files in a **DREAM Lab Coder workspace** using `gemini-3.5-transcribe` through the DREAM Lab LiteLLM gateway (`https://litellm.dreamlab.ucsb.edu`).

## Why Use the Gemini `generateContent` API Instead of `/v1/audio/transcriptions`

While the OpenAI-compatible `/v1/audio/transcriptions` endpoint only returns a plain text string (`{"text": "..."}`), calling `gemini-3.5-transcribe` via the native Gemini API (`/v1beta/models/gemini-3.5-transcribe:generateContent` using the `google-genai` SDK) unlocks **`AudioTranscriptionConfig`**:

- **Native Word-Level Timestamps (`word_timestamp=True`):** Returns exact `start_offset` and `end_offset` (e.g., `"1.400s"`, `"1.500s"`) for every word in a single pass—no secondary short-window alignment pass required.
- **Speaker Diarization (`diarization=True`):** Splits the response into `Part` objects per speaker turn, each with `part.audio_transcription.speaker_label` (e.g., `"spk:0"`, `"spk:1"`) and its corresponding `words` array.
- **Transcription Mode (`mode="VERBATIM"` or `"SMART"`):**
  - `VERBATIM` (default): Exact transcription; compatible with `word_timestamp=True` and `diarization=True`.
  - `SMART`: Removes disfluencies/filler words and applies automatic formatting *(note: `word_timestamp` and `diarization` are only supported in `VERBATIM` mode)*.
- **Language Hints & Custom Vocabulary (`language_codes`, `custom_vocabulary`):** Bias recognition toward specific BCP-47 languages or domain terms.

---

## Gateway Configuration & Pricing

- **Base URL:** `https://litellm.dreamlab.ucsb.edu`
- **Endpoint:** `/v1beta/models/gemini-3.5-transcribe:generateContent` (via `google-genai` SDK)
- **Model:** `gemini-3.5-transcribe`
- **API Key:** Loaded from `$DREAMLAB_LLM_KEY` or `~/.config/dreamlab/llm.env`
- **Segment Limit:** Maximum **15 minutes (`900s`)** per audio request.
- **Pricing (`gemini-3.5-transcribe`):**
  - **Audio Input:** `$2.00` per 1M audio tokens (`$0.000002` / token, or `$0.003` / minute at 25 tokens/sec)
  - **Text Output:** `$12.00` per 1M text tokens (`$0.000012` / token)
  - A single-pass transcription with native word timestamps and diarization costs **~$0.006 per minute** of audio (~$0.29 for a 51-minute recording).

---

## Quick Start: Bundled Transcription Script

Run the bundled `scripts/transcribe.py` script via `uv run` (PEP 723 inline dependencies install `google-genai` automatically):

```bash
SKILL_DIR=<directory containing this SKILL.md>
uv run "$SKILL_DIR/scripts/transcribe.py" path/to/audio.mp3 --output-dir .
```

### Common Options

```bash
uv run "$SKILL_DIR/scripts/transcribe.py" path/to/audio.mp3 \
  --output-dir . \
  --title "Recording Title" \
  --chunk-duration 720 \
  --overlap 60 \
  --segment-interval 30 \
  --include-speakers \
  --vocab "AI4LAM" \
  --language "en-US"
```

- `--chunk-duration` (default `720`): Chunk length in seconds (12 minutes, safely under the 15-minute limit).
- `--overlap` (default `60`): Overlap between consecutive chunks in seconds for seamless boundary stitching.
- `--segment-interval` (default `30`): Target paragraph duration in seconds before breaking at the next sentence boundary.
- `--include-speakers`: Include `(spk:0)` speaker labels in `transcript.md` / `transcript.txt` and start a new paragraph when the speaker changes.
- `--no-diarization`: Disable speaker diarization.
- `--vocab` / `--language`: Repeatable flags passed to `AudioTranscriptionConfig(custom_vocabulary=..., language_codes=...)`.

### Outputs
- `transcript.md` — Formatted Markdown with `**[MM:SS]**` paragraph timestamps
- `transcript.txt` — Plain text with `[MM:SS]` paragraph prefixes
- `transcript.json` — Structured JSON containing:
  - `segments`: Paragraph segments with `start`, `end`, `timestamp`, `speaker`, and `text`
  - `words`: Complete array of every word with exact `start`, `end` (in seconds), and `speaker`
  - `full_text`: Complete stitched transcript text
  - `usage`: Audio input tokens, text output tokens, and `estimated_cost_usd`
- `chunks/` & `cache/` — Extracted audio chunks and cached JSON responses (making runs idempotent and resumable; add `chunks/` and `cache/` to `.gitignore`)

---

## Core Implementation Pattern

### 1. Calling `gemini-3.5-transcribe` with `google-genai`

Configure `genai.Client` with `base_url="https://litellm.dreamlab.ucsb.edu"` and pass `Authorization: Bearer $DREAMLAB_LLM_KEY` in `HttpOptions.headers`:

```python
from google import genai
from google.genai import types

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        base_url="https://litellm.dreamlab.ucsb.edu",
        headers={"Authorization": f"Bearer {api_key}"},
    ),
)

resp = client.models.generate_content(
    model="gemini-3.5-transcribe",
    contents=[
        types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3")
    ],
    config=types.GenerateContentConfig(
        audio_transcription_config=types.AudioTranscriptionConfig(
            word_timestamp=True,
            diarization=True,
            mode=types.AudioTranscriptionConfigMode.VERBATIM,
        )
    ),
)

for part in resp.candidates[0].content.parts:
    at = part.audio_transcription
    # at.speaker_label -> e.g. "spk:0"
    # at.text          -> transcript text for this speaker turn
    # at.words         -> list of WordInfo(word="...", start_offset="1.400s", end_offset="1.500s")
```

### 2. Overlapping Audio Chunking (< 15-Minute Limit)
For audio files longer than 15 minutes (`900s`):
1. Query total duration with `ffprobe`.
2. Slice the audio into **12-minute (`720s`) chunks with a 60-second overlap** (`step = 660s`) using `ffmpeg -y -ss <start> -t <duration> -i <audio> -c copy <chunk_path>`.
3. Transcribe all chunks concurrently using `ThreadPoolExecutor`.
4. Add each chunk's start time (`chunk_start`) to every word's parsed `start_offset` and `end_offset` so all words share a global timeline in seconds.

### 3. Stitching Overlapping Chunks with Native Word Timestamps
To splice chunk $A$ (ending at `boundary_start + overlap`) and chunk $B$ (starting at `boundary_start`) without duplicating or dropping words:
1. Isolate the words in $A$ and $B$ whose timestamps fall within the overlap window `[boundary_start - 5s, boundary_start + overlap + 5s]`.
2. Normalize the word tokens (`re.sub(r"[^a-z0-9]", "", w.lower())`) and align them using `difflib.SequenceMatcher(None, norm_a, norm_b, autojunk=False)`.
3. Find the longest contiguous matching block ($\ge 3$ words) and **splice at its midpoint** (`mid = best.size // 2`): keep words from $A$ up to `tail_start_idx + best.a + mid` and continue with words from $B$ starting at `best.b + mid`.
4. If no multi-word match is found (e.g., silence across the overlap), fall back to splitting at the exact timestamp midpoint `boundary_start + overlap / 2`.
