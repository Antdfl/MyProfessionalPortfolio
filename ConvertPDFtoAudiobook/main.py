"""
PDF to Audiobook Converter
--------------------------
Reads a PDF file, optionally translates its text, and converts it to an MP3
audiobook using Google Text-to-Speech (gTTS).

Pipeline:
  1. Collect user inputs (paths, languages).
  2. Extract raw text from the PDF page by page (PyPDF2).
  3. Translate the text if the source and target languages differ (deep-translator).
  4. Split the text into API-safe chunks and convert each one to audio (gTTS).
  5. Stream all audio chunks into a single in-memory buffer and save as MP3.

Dependencies: PyPDF2, deep-translator, gTTS
"""

import os
import PyPDF2
from deep_translator import GoogleTranslator  # wrapper around Google Translate API
from gtts import gTTS, gTTSError              # gTTSError lets us catch 429 rate-limit responses
from pathlib import Path
import io                                     # for the in-memory audio buffer
import time                                   # for sleep() used in retry backoff

# Resolve the directory that contains this script so all file paths are
# relative to it regardless of the working directory the user launches from.
db_path = Path(__file__).parent

# Both GoogleTranslator and gTTS communicate with remote Google APIs that
# reject requests longer than ~5 000 characters. 4 500 gives a comfortable
# safety margin while still keeping the number of round-trips low.
CHUNK_SIZE = 4500

# How many times to retry a chunk after a 429 before giving up.
# Each retry waits RETRY_BASE_WAIT * attempt_number seconds (5s, 10s, 15s …)
# so the total possible wait before failure is 5+10+15+20 = 50 seconds.
RETRY_ATTEMPTS = 4
RETRY_BASE_WAIT = 5  # seconds

# Minimum pause between every successful chunk request (prevention layer).
# Even one second is usually enough to stay below Google's rate limit.
REQUEST_DELAY = 1  # seconds


def tts_with_retry(chunk, lang, buffer):
    """
    Convert one text chunk to MP3 and append it to `buffer`.

    Two-layer protection against the 429 Too Many Requests error:
      1. Prevention  — REQUEST_DELAY seconds of sleep after every successful
                       request keeps the request rate below Google's threshold.
      2. Recovery    — if a 429 still occurs, catch it and wait progressively
                       longer before each retry (5s, 10s, 15s …). This is
                       called exponential-style backoff.
    """
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            tts = gTTS(chunk, lang=lang)
            tts.write_to_fp(buffer)
            # Prevention: pause after every successful request.
            time.sleep(REQUEST_DELAY)
            return
        except gTTSError as e:
            if '429' in str(e) and attempt < RETRY_ATTEMPTS:
                # Recovery: wait longer with each failed attempt, then retry.
                wait = RETRY_BASE_WAIT * attempt
                print(f"\n      Rate limited — waiting {wait}s (retry {attempt}/{RETRY_ATTEMPTS - 1})...")
                time.sleep(wait)
            else:
                # Either a different error, or we exhausted all retries.
                raise


def split_text(text, max_chars=CHUNK_SIZE):
    """
    Break a long string into a list of smaller chunks, each no longer than
    `max_chars` characters, splitting preferably at sentence boundaries.

    Strategy (in priority order):
      1. Split at the last '. ' (end of sentence) before the limit  →  clean break.
      2. Fall back to the last space before the limit               →  mid-paragraph break.
      3. Hard-cut at the limit character if no whitespace is found  →  last resort.

    This keeps sentences intact whenever possible, which matters for both
    translation quality and natural-sounding TTS output.
    """
    chunks = []
    while len(text) > max_chars:
        # Prefer splitting after a full stop so the chunk ends on a complete sentence.
        split_at = text.rfind('. ', 0, max_chars)

        if split_at == -1:
            # No sentence boundary found — split at the last word boundary instead
            # to avoid cutting a word in half.
            split_at = text.rfind(' ', 0, max_chars)

        if split_at == -1:
            # No whitespace at all (e.g. a very long URL or token) — hard cut.
            split_at = max_chars

        # `split_at` is the index of the split character (period or space).
        # Python slicing is exclusive on the right, so [:split_at] would stop
        # *before* that character. [:split_at + 1] includes it, keeping the
        # period at the end of the chunk so sentences read naturally.
        # Example with split_at = 10 on "Hello world. Next sentence":
        #   text[:11] → "Hello world."   ← chunk stored (period kept)
        #   text[11:] → " Next sentence" ← remainder (leading space stripped below)
        chunks.append(text[:split_at + 1].strip())

        # Advance past the split character so the next iteration starts on
        # fresh text. .strip() removes the leading space that follows the
        # period (or the space itself when splitting on a word boundary).
        text = text[split_at + 1:].strip()

    # Append whatever text remains after the last split (always less than max_chars).
    if text:
        chunks.append(text)

    return chunks


# ---------------------------------------------------------------------------
# Step 0 — Collect user inputs
# ---------------------------------------------------------------------------
# Language codes follow the BCP-47 / ISO 639-1 standard used by Google:
#   'en' = English, 'it' = Italian, 'es' = Spanish, 'fr' = French, etc.
pdf_language = input("Enter the language of the PDF (e.g., 'en' for English, 'it' for Italian, 'es' for Spanish): ")
pdf_file = input("Enter the name of the PDF file (including the .pdf extension): ")
output_language = input("Enter the language for the audiobook (e.g., 'en' for English, 'it' for Italian, 'es' for Spanish): ")
output_audiobook_name = input("Enter the name for the output audiobook (without extension): ")


# ---------------------------------------------------------------------------
# Step 1 — Validate the PDF path
# ---------------------------------------------------------------------------
# Build an absolute path by joining the script directory with the filename
# provided by the user. This means the PDF must sit in the same folder as
# this script (or the user can type a relative/absolute path themselves).
pdf_path = db_path / pdf_file
if not pdf_path.is_file():
    print(f"Error: The file '{pdf_path}' does not exist.")
    exit(1)


# ---------------------------------------------------------------------------
# Step 2 — Extract text from the PDF page by page
# ---------------------------------------------------------------------------
# PyPDF2 opens the file in binary mode ('rb') because PDF is a binary format.
# extract_text() returns a plain string for each page; 'or ""' guards against
# pages that contain only images and return None.
print("\n[1/3] Extracting text from PDF...")
pages_text = []
with open(pdf_path, 'rb') as f:
    pdf_reader = PyPDF2.PdfReader(f)
    total_pages = len(pdf_reader.pages)
    for i, page in enumerate(pdf_reader.pages, 1):
        # \r (carriage return) moves the cursor back to the start of the line
        # so each update overwrites the previous one instead of scrolling.
        print(f"      Page {i}/{total_pages}", end='\r')
        pages_text.append(page.extract_text() or '')

print(f"      Done — {total_pages} pages extracted.      ")

# Join all pages with a space so the last word of one page and the first word
# of the next are not merged into a single unreadable token.
full_text = ' '.join(pages_text)


# ---------------------------------------------------------------------------
# Step 3 — Translate the text (only when source and target languages differ)
# ---------------------------------------------------------------------------
if pdf_language != output_language:
    print("\n[2/3] Translating text...")

    # Split before translating: GoogleTranslator will raise an error if the
    # input exceeds its per-request character limit.
    chunks = split_text(full_text)
    translated = []
    total = len(chunks)

    for i, chunk in enumerate(chunks, 1):
        print(f"      Chunk {i}/{total}", end='\r')
        # A new GoogleTranslator instance is created per chunk; the library is
        # stateless so this has no overhead.
        translated.append(
            GoogleTranslator(source=pdf_language, target=output_language).translate(chunk)
        )

    # Reassemble the translated chunks into a single string.
    full_text = ' '.join(translated)
    print(f"      Done — {total} chunks translated.      ")
else:
    # Source and target languages are the same — skip the translation API call.
    print("\n[2/3] No translation needed.")


# ---------------------------------------------------------------------------
# Step 4 — Convert text to speech, chunk by chunk
# ---------------------------------------------------------------------------
# gTTS makes one HTTPS request per gTTS() call. Processing in chunks:
#   • avoids the per-request size limit that causes silent failures on long text
#   • lets us show granular progress to the user
#
# audio_buffer is a single in-memory binary stream. write_to_fp() appends the
# raw MP3 bytes from each chunk directly into it. Because MP3 is a frame-based
# format, concatenated frames play back seamlessly in any standard MP3 player.
print("\n[3/3] Generating audio...")
chunks = split_text(full_text)
total = len(chunks)
audio_buffer = io.BytesIO()  # acts as an in-memory file — no temp files on disk

# enumerate(chunks, 1) iterates over the list giving both the index and the
# value at the same time, unpacked into two variables: i (position) and chunk
# (the text). The second argument, 1, makes the counter start at 1 instead of
# the default 0, so the progress display reads "Chunk 1/9, 2/9 ..." naturally.
# It is equivalent to maintaining a manual counter but in a single clean line:
#   i = 0
#   for chunk in chunks:
#       i += 1
for i, chunk in enumerate(chunks, 1):
    print(f"      Chunk {i}/{total}", end='\r')
    # tts_with_retry handles both the API call and rate-limit protection.
    tts_with_retry(chunk, output_language, audio_buffer)

print(f"      Done — {total} chunks converted.      ")


# ---------------------------------------------------------------------------
# Step 5 — Write the final MP3 file to disk
# ---------------------------------------------------------------------------
output_path = db_path / f'{output_audiobook_name}.mp3'

# getvalue() retrieves the entire byte content accumulated in the buffer.
with open(output_path, 'wb') as f:
    f.write(audio_buffer.getvalue())

print(f"\nAudiobook saved: {output_path}")
