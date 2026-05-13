# Project Retrospective — PDF to Audiobook Converter

**Author:** Antonio Di Felice
**Date:** May 2026
**Platform:** Python command-line script

---

## Project Overview

A Python script that accepts a PDF file and converts its text to an MP3 audiobook, with optional translation between languages. The tool provides real-time progress feedback at each stage of the pipeline.

---

## What Went Well

- Delivered a working end-to-end pipeline from PDF to playable MP3 in a single script.
- Made an informed library choice by evaluating three TTS alternatives before committing (see below).
- Identified and resolved a non-trivial API reliability issue (rate limiting) without switching libraries.
- Kept dependencies minimal: three pip packages, no external binaries, no paid services.
- Evolved the interface from interactive prompts to a full CLI (`argparse`) while preserving complete backward compatibility.
- All four planned test scenarios passed, including one unplanned mixed-path scenario discovered during testing.

---

## Implementation Challenges

### 1. The script silently hung on large PDFs

The first working proof-of-concept passed the entire extracted text to `gTTS` in a single call. For short PDFs it worked fine. For anything longer it simply hung — no error, no output, no timeout. The root cause was that Google's TTS API has an undocumented character limit of approximately 5 000 per request and silently drops oversized payloads.

**Resolution:** Implemented a `split_text()` function that splits the full text into chunks of 4 500 characters, preferring sentence boundaries over word boundaries over hard cuts, to stay safely within the API limit.

**Lesson learned:** Never assume a third-party API or library handles large inputs gracefully. Read the documentation for limits first; when limits are undocumented, test at the boundary before writing production logic.

---

### 2. No feedback during long-running operations

The original script gave no output while processing. For a large PDF the user faced a blank terminal for minutes with no indication of whether the script was still running or had stalled.

**Resolution:** Added per-stage progress lines using `\r` (carriage return) so each page and each chunk update overwrites the same terminal line rather than scrolling. Three numbered labels (`[1/3]`, `[2/3]`, `[3/3]`) communicate overall pipeline position.

**Lesson learned:** Progress feedback is a basic usability requirement even for command-line tools. Silent long-running scripts erode user confidence and make debugging harder.

---

### 3. 429 Too Many Requests error from the gTTS API

After introducing chunking, the script started hitting Google's rate limiter when converting longer documents. Chunking solved the per-request size problem but introduced a new one: sending many requests in rapid succession triggered HTTP 429 responses.

**Resolution:** Implemented a two-layer defence in a dedicated `tts_with_retry()` function:

- **Prevention** — a 1-second pause after every successful request keeps the throughput below Google's threshold.
- **Recovery** — a `gTTSError` 429 is caught and retried up to four times with exponential backoff (5 s, 10 s, 15 s, 20 s) before re-raising.

**Lesson learned:** Rate limiting is a standard concern whenever a loop makes repeated calls to an external API. The correct pattern — a fixed delay for prevention plus exponential backoff for recovery — should be considered a default, not an afterthought.

---

### 4. A subtle variable naming bug caused a doubled file path

The original code reused the variable `pdf_file` for two different things: first as the raw filename string entered by the user, then as the resolved `Path` object. A later `open(db_path / pdf_file, 'rb')` call then combined the script directory with an already-absolute path, silently producing a wrong path.

**Resolution:** Renamed the resolved path to `pdf_path` to keep the two values distinct.

**Lesson learned:** Variable names should reflect what the value *is*, not where it came from. Reusing a name for a different type of data is a reliable source of subtle bugs that are hard to spot in code review.

---

### 5. Evaluating TTS alternatives took longer than expected

Before settling on gTTS three libraries were evaluated:

| Library | Verdict |
| --- | --- |
| **pyttsx3** | Fast and offline, but voice quality is robotic — unsuitable for long listening sessions |
| **Kokoro / Coqui TTS** | Near-human quality offline neural TTS, but requires a ~350 MB model download and a PyTorch runtime — too much setup complexity for this scope |
| **gTTS** | Best balance: natural-sounding output, zero cost, three-line integration |

There was also a brief misconception that Kokoro required payment because its model is hosted on Hugging Face, which has a paid tier. It is in fact fully open-source under the Apache 2.0 licence.

**Lesson learned:** Library evaluation is time well spent, but scope the evaluation early. Define the decision criteria (voice quality, offline capability, setup cost) before researching options so the comparison stays focused.

---

### 6. Virtual environment not activated caused ModuleNotFoundError

When launching the script from a terminal outside VS Code, Python could not find `PyPDF2` or any other project dependency. The libraries were installed correctly but only inside the project's `.venv` virtual environment, which was not active in the external shell.

**Resolution:** Activated the virtual environment before running the script:
`e:\code\MyProfessionalPortfolio\.venv\Scripts\activate`

**Lesson learned:** A virtual environment must be explicitly activated in every new terminal session. This is standard Python project hygiene and should be documented in the README — which it now is.

---

### 7. Path resolution: script directory vs. current working directory

When launching the script from a different directory than where `main.py` lives, relative filenames were initially resolving to the wrong folder (the CWD), causing a file-not-found error even when the PDF was correctly placed next to the script.

**Resolution:** Changed path resolution so that relative filenames always resolve from the script's own directory (`Path(__file__).parent`), while absolute paths are passed through unchanged. This matches how most users intuitively expect the tool to behave.

**Lesson learned:** CWD-relative paths are the standard for general-purpose CLI tools, but for a script that is tightly coupled to a fixed working folder, resolving from the script directory is more predictable. The right choice depends on the tool's intended usage pattern — and should be tested explicitly.

---

### 8. Interactive input() limits automation — replaced with argparse

The original `input()` prompts required a human at the keyboard for every run, making the script impossible to automate, schedule, or chain with other tools.

**Resolution:** Added `argparse` with all four arguments optional and a fallback to `input()` for any that are missing. This preserves the original interactive behaviour while also enabling fully automated runs:

```bash
python main.py --file book.pdf --from-lang en --to-lang it --output audiobook
```

**Lesson learned:** `argparse` should be the default choice for any Python script that a user will run from the command line — even for simple scripts. The interactive fallback pattern (`args.value or input(...)`) costs one extra line per argument and adds significant usability value.

---

## Test Plan & Results

Four path-resolution scenarios were designed and executed to validate the `argparse` interface and the file path logic.

| # | Scenario | Input path | Output path | Expected result | Actual result |
| --- | --- | --- | --- | --- | --- |
| 1 | VS Code terminal | Relative — `bookb.pdf` next to `main.py` | Relative — script folder | MP3 in script folder | OK |
| 2 | External terminal from Documents | Relative — `bookb.pdf` next to `main.py` | Relative — script folder | MP3 in script folder | OK |
| 3 | Absolute input, relative output | Absolute — `C:\Users\ilpot\OneDrive\Documenti\bookdoc.pdf` | Relative — script folder | MP3 in script folder | OK |
| 4 | Fully absolute | Absolute — `C:\Users\ilpot\OneDrive\Documenti\bookdoc.pdf` | Absolute — `C:\Users\ilpot\OneDrive\Documenti\audiobook_it` | MP3 at specified path | OK* |

\* Test 4 triggered the gTTS rate limiter at chunk 8/10. The retry mechanism fired correctly (5 s → 10 s → 15 s backoff) but the request was rejected after exhausting all retries. The path routing worked as intended — the failure was a network/API reliability issue, not a code defect. Increasing `RETRY_ATTEMPTS` or `REQUEST_DELAY` in `main.py` would mitigate this for longer documents.

**Unplanned scenario discovered during testing:** test 3 was inadvertently run with absolute input and relative output before the fully absolute test. It passed without any code changes, confirming that input and output paths are resolved independently. This became the de facto scenario 3 and pushed the originally planned scenario 3 to position 4.

### Final Considerations

- The retry mechanism works but has a ceiling: on long documents under heavy API load, exhausting all retries is a real risk. A configurable retry count via `--retries` argument would be a practical improvement.
- The virtual environment activation step is a friction point for non-technical users. Packaging the script with a `.bat` launcher that activates the venv and runs the script in one double-click would significantly improve usability on Windows.
- Testing revealed that the error messages added during development (`Looking in: ...`, `Working directory: ...`) were genuinely useful for diagnosing path problems — confirming that diagnostic output belongs in the tool, not just in the developer's head.

---

## Architectural Observations for Future Projects

These are patterns that would improve the design if the project were to grow or be used in a production context:

**`argparse` — implemented**
Added during this project. The interactive fallback pattern proved to be the right approach: zero regression for existing users, full automation capability for new ones.

**Centralise configuration**
Constants like `CHUNK_SIZE`, `RETRY_ATTEMPTS`, and `REQUEST_DELAY` are currently defined at module level. In a larger script they would belong in a configuration file or dataclass so they can be changed without editing the source.

**Replace `print()` with the `logging` module**
The current progress output is mixed with error output and is impossible to silence or redirect. The `logging` module provides levels (`INFO`, `WARNING`, `ERROR`) and lets callers control verbosity without modifying the script.

**Consider a pipeline / strategy pattern**
The script is a linear sequence of steps. If new steps were added (e.g. OCR fallback for image-only PDFs, different TTS backends) a pipeline pattern with pluggable stages would be more maintainable than growing a single script.

**Parallel chunk processing**
Translation and TTS chunks are currently processed sequentially. Since each chunk is independent, they could be processed concurrently with `concurrent.futures.ThreadPoolExecutor`, significantly reducing total runtime for long documents. Rate-limit handling would need to be adapted accordingly.

---

## Summary

The core challenge of this project was not the happy path — a basic PDF-to-audio conversion is a few lines. The real engineering work was handling the failure modes: silent API limits, rate limiting, variable aliasing bugs, and missing user feedback. Each of these was a concrete lesson in defensive programming and API integration discipline.
