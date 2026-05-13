# PDF to Audiobook Converter

A Python command-line tool that converts any PDF file into an MP3 audiobook, with optional translation into a different language.

---

## Requirements

Given a PDF file, the tool must:

1. Accept user inputs: PDF filename, PDF language, output language, output filename.
2. Extract all readable text from the PDF.
3. Translate the text when the source and target languages differ.
4. Convert the text to natural-sounding speech and save it as an MP3 file.
5. Display progress at each stage so the user is never left waiting without feedback.

---

## Functional Analysis

### Library Selection

The project deliberately avoids paid cloud APIs (AWS Polly, Google Cloud TTS) in favour of lightweight Python libraries that are free and easy to maintain.

| Concern | Library chosen | Reason |
| --- | --- | --- |
| PDF text extraction | [PyPDF2](https://pypi.org/project/PyPDF2/) | Pure-Python, no external binaries required |
| Translation | [deep-translator](https://pypi.org/project/deep-translator/) | Thin wrapper over Google Translate; supports 100+ language pairs |
| Text-to-speech | [gTTS](https://pypi.org/project/gTTS/) | Uses Google's neural TTS engine; natural-sounding output; free |

### TTS Library Comparison

Before committing to gTTS, two alternatives were evaluated:

**pyttsx3** — works fully offline using the OS-native speech engine (SAPI5 on Windows). Fast and reliable, but the voice quality is robotic and fatiguing for long listening sessions.

**Kokoro / Coqui TTS** — open-source neural TTS that runs offline and produces near-human quality audio. Ruled out for this project because it requires downloading a ~350 MB model and a PyTorch runtime, adding significant setup complexity.

**Decision: gTTS** — best balance of voice quality, ease of integration, and zero cost. The reliability concern (rate limiting) was addressed at the implementation level (see below).

---

## Implementation

### Processing Pipeline

```text
User input
    │
    ▼
Validate PDF path
    │
    ▼
Extract text page by page (PyPDF2)
    │
    ▼
Translate in chunks if needed (deep-translator)
    │
    ▼
Convert to audio in chunks (gTTS) ──► in-memory BytesIO buffer
    │
    ▼
Write MP3 to disk
```

### Key Technical Decisions

**Chunking (4 500 characters per chunk)**
Both the Google Translate and gTTS APIs silently fail or raise errors on inputs larger than ~5 000 characters. The full PDF text is split at sentence boundaries (falling back to word boundaries, then a hard cut) before every API call. Chunks are reassembled after translation and streamed into a single audio buffer after TTS.

**In-memory audio assembly**
Each gTTS chunk is written directly to a shared `io.BytesIO` buffer via `write_to_fp()` rather than saving temporary files to disk. MP3 is a frame-based format, so appending frames from consecutive chunks produces a seamlessly playable file.

**Rate-limit handling (two-layer)**

- *Prevention*: a 1-second pause after every successful TTS request keeps the request rate within Google's undocumented threshold.
- *Recovery*: a `gTTSError` 429 is caught and retried up to 4 times with exponential backoff (5 s, 10 s, 15 s, 20 s) before the error is re-raised.

**Progress display**
Each of the three pipeline stages reports per-page or per-chunk progress using `\r` (carriage return) so updates overwrite the same terminal line rather than scrolling.

---

## Usage

Place the PDF file in the same directory as `main.py`, then run:

```bash
python main.py
```

The script will prompt for:

```text
Enter the language of the PDF (e.g., 'en', 'it', 'es'):
Enter the name of the PDF file (including the .pdf extension):
Enter the language for the audiobook (e.g., 'en', 'it', 'es'):
Enter the name for the output audiobook (without extension):
```

The output MP3 is saved in the same directory.

### Dependencies

```bash
pip install PyPDF2 deep-translator gTTS
```
