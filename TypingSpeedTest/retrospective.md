# Project Retrospective — Typing Speed Test

**Author:** Antonio Di Felice  
**Date:** April 2026  
**Platform:** Desktop — Python / Tkinter (Windows/macOS/Linux)

---

## Project Overview

A desktop GUI application that measures typing speed in real time, built entirely with Python's standard library (no third-party dependencies). The game presents a sample text, starts a 60-second countdown on the first keystroke, and produces a detailed end-of-game summary showing CPM, WPM and a word-by-word error report.

**Tech stack:** Python · Tkinter · Standard library only (`tkinter`, `random`)  
**Architecture:** Single-class MVC-style design (`TypingSpeedTest` controller + `data.py` text pools)

---

## Part 1 — Design and Prototyping

### Approach: screenshot-driven design

Rather than designing the UI from scratch, the layout was derived from screenshots of an existing typing-speed reference site. This approach offered two practical advantages: it provided an immediate, tested UX baseline to work from, and it reduced the design decision space to implementation details rather than product decisions.

The three reference screenshots (`main_app.png`, `too_many_wrong_chars.png`, `game_summary.png`) were
used as a contract for the three distinct states the application needed to render:

| State | Description |
|---|---|
| **Main / Restart** | Stats bar + sample text panel + typing input field |
| **Error interrupt** | Modal popup when typed characters exceed expected word length by >10 |
| **Game summary** | Full-screen CPM/WPM results + per-word error breakdown |

### Specification before coding

Before writing a single line of implementation, a detailed `README.md` was produced covering layout mapping, business rules (word submission via space bar, not Enter), edge-case behaviour (excessive wrong characters, Enter-key misuse), and the data strategy (bilingual text pools via a companion `data.py` module). This upfront specification discipline significantly reduced ambiguity during development and made AI-assisted generation of the initial scaffold substantially more accurate.

---

## Part 2 — Implementation Challenges

### Challenge 1: Real-time typing analysis in a single-threaded event loop

Tkinter is single-threaded — the GUI event loop, the timer countdown, and the keystroke analysis all share the same thread. This creates a risk of the UI freezing if any callback takes too long, and requires careful sequencing of timer ticks versus input events.

The core design decision was to perform all analysis **synchronously on each `<KeyRelease>` event** rather than spawning background threads. Word boundary detection (space bar press), character
highlighting, and WPM recalculation all execute within the same callback. Keeping each callback short and side-effect-free (no I/O, no blocking calls) was sufficient to keep the UI responsive for the
duration of a 60-second game.

**Lesson:** For short-lived desktop tools where input frequency is human-bounded (< ~10 keystrokes/sec),
synchronous event callbacks are simpler and more reliable than threading — threads introduce
synchronisation overhead that is only justified when callbacks perform genuinely slow work.

---

### Challenge 2: Timer synchronisation — `after()` vs wall-clock time

Tkinter's `after(ms, callback)` schedules a callback after approximately `ms` milliseconds, but is not
precise: if the event loop is busy (e.g., during a blocking callback), the tick fires late. Relying on
`after(1000, tick)` as the sole time source accumulates drift over a 60-second round.

The mitigation is to record the **wall-clock start time** (`time.time()`) on the first keystroke and
compute elapsed time on each tick as `now - start_time`, rather than incrementing a counter. This
makes the timer resilient to scheduling jitter regardless of how many `after()` ticks are delayed.

**Lesson:** Never use repeated `after()` calls as a precise elapsed-time source. Use them only to
trigger a refresh; derive the displayed value from a wall-clock delta.

---

### Challenge 3: Per-character highlighting with Tkinter `Text` tags

Tkinter's `Text` widget supports named **tags** that apply colour, font, and other styling to arbitrary
character ranges. Using tags for real-time highlighting (correct word = green, wrong word = red,
upcoming words = neutral) required careful management of tag application order, since overlapping tags
apply in the order they were created — not in the order they are applied to a range.

The solution was to define a fixed tag priority order at initialisation (`already_correct`,
`already_wrong`, `current_ok`, `current_err`, `upcoming`) and rebuild all tag ranges from scratch on
every keystroke rather than attempting incremental updates. While this is O(n) in the number of words,
it is imperceptible for texts of ≤ 200 words and eliminates an entire class of stale-tag bugs.

---

### Challenge 4: Word boundary and error detection edge cases

Two user-input scenarios required explicit guard logic:

1. **Excessive wrong characters:** If the user's typed prefix exceeds the correct word's length by more
   than 10 characters, they have likely lost track of word boundaries. A modal popup interrupts the
   game and prompts a restart, preventing the score from becoming meaningless.

2. **Enter key misuse:** Pressing Enter instead of Space is a common habit from form-filling contexts.
   The application detects Enter presses, shows a contextual warning, and records the occurrence — the
   end-of-game summary reminds the user if they used Enter at least once, with a note that the habit
   typically reduces WPM.

Both rules were specified in the README before implementation, which made the edge-case logic
unambiguous to implement and test.

---

### Challenge 5: WPM / CPM calculation accuracy

The standard definition of WPM uses a fixed word length of 5 characters (i.e., `total_chars_typed / 5 /
elapsed_minutes`). CPM is `total_chars_typed / elapsed_minutes`. Both metrics are only meaningful for
**correctly typed** characters — including errors inflates the score artificially.

The implementation tracks correct-word character count separately from total keystrokes, so WPM and CPM
reflect only the text that matched the reference. The per-word error list at game-end surfaces exactly
what the user typed versus what was expected, giving actionable feedback rather than just a number.

---

## Part 3 — Architecture Decisions

### Separation of data from logic (`data.py`)

Text samples for both languages are stored in `data.py` as plain Python lists (`TEXTS_EN`, `TEXTS_IT`),
imported by `main.py`. This separation means:

- Adding new text samples or languages requires editing only `data.py` — zero changes to game logic.
- The game logic module can be unit-tested independently of the text content.
- `data.py` is trivially replaceable with a file/database loader in a future version.

### Zero external dependencies

The entire application runs on Python's standard library. No `pip install` is needed — the user clones
the repository and runs `python main.py`. This was a deliberate constraint that maximises portability
and eliminates dependency management as a maintenance burden for a tool of this scope.

---

## Part 4 — Lessons Learned Summary

| Area | Lesson |
|---|---|
| **Specification** | A detailed README written before coding reduces ambiguity and makes AI-assisted scaffolding significantly more accurate. The spec doubles as living documentation. |
| **GUI threading** | For human-speed input, synchronous event callbacks are simpler and safer than threading. Reach for threads only when callbacks perform blocking I/O or heavy computation. |
| **Timer accuracy** | Use `after()` only to trigger display refreshes. Derive elapsed time from a wall-clock delta (`time.time() - start`) to avoid drift accumulation. |
| **Tkinter tags** | Rebuild tag ranges from scratch on each update rather than patching incrementally. The O(n) cost is negligible for small texts; the correctness guarantee is significant. |
| **UX edge cases** | Explicitly specifying edge-case behaviour (Enter key, excessive errors) in the design phase prevents ambiguous implementation and produces a more polished user experience. |
| **Metric accuracy** | Track correct-character count separately from total keystrokes. Reporting only correct-text speed gives the user meaningful, honest feedback. |

---

## Part 5 — Skills Demonstrated

- **Tkinter GUI development:** widget layout, event binding, `Text` tag management, `after()`-based animation loops, modal dialogs.
- **Real-time event-driven programming:** keystroke analysis, timer synchronisation, state machine management across three distinct application states.
- **Software design:** requirements-first development, separation of data from logic, zero-dependency architecture.
- **User experience thinking:** error interrupts, contextual warnings, end-of-game feedback designed to be instructive rather than just numeric.
