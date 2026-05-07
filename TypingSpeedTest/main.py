"""
Typing Speed Test
=================
A desktop GUI game built with Tkinter that measures how fast a user can type.

How it works
------------
1. The app shows a sample sentence in the upper panel.
2. The user types in the lower input field.
3. The 60-second countdown starts on the first keystroke.
4. Each word is submitted by pressing the SPACE bar.
5. After time runs out the user finishes the current word, then a summary
   screen replaces the text panel showing CPM, WPM, and every mistake made.

Run with:
    python main.py

Dependencies: only the Python standard library (tkinter).
"""

import tkinter as tk
from tkinter import messagebox
import random

# Import the sample text pools from the companion module.
# Keeping text data separate makes it easy to add or translate phrases
# without touching the game logic.
from data import TEXTS_EN, TEXTS_IT

# ── Game settings ─────────────────────────────────────────────────────────────

GAME_DURATION = 60  # Total seconds for one round.

# ── Colour palette ────────────────────────────────────────────────────────────
# All colours are defined here so you can restyle the whole app from one place.

BG       = "#f0f0f0"  # Window / stats-bar background (light grey).
WHITE    = "#ffffff"  # Text-display panel background.
INPUT_BG = "#e8f5e9"  # Typing field background (pale green).
GRN_BG   = "#a8d8a8"  # Highlight for the current word when input is correct.
RED_BG   = "#f4a0a0"  # Highlight for the current word when input is wrong.
GRN_FG   = "#2e7d32"  # Foreground colour for already-typed correct words.
RED_FG   = "#c62828"  # Foreground colour for already-typed wrong words.
PH_FG    = "#aaaaaa"  # Placeholder text colour (muted grey).

# ── Font definitions ──────────────────────────────────────────────────────────
# Tkinter fonts are 3-tuples: (family, size) or (family, size, style).

F_STATS  = ("Helvetica", 11)            # Stats bar labels.
F_TEXT   = ("Helvetica", 22, "bold")    # Sample text displayed in the game.
F_INPUT  = ("Helvetica", 18)            # User typing field.
F_SUM_H  = ("Helvetica", 18, "bold")    # Summary screen headline.
F_SUM    = ("Helvetica", 12)            # Summary screen body text.
F_SUM_W  = ("Helvetica", 12, "italic")  # Summary screen "Enter key" warning.


# ── Main application class ────────────────────────────────────────────────────

class TypingSpeedTest:
    """Manages the entire Typing Speed Test application.

    Responsibilities
    ----------------
    * Build the three-row Tkinter layout (stats bar / text display / input).
    * Track game state: current word index, timer, typed history, scores.
    * Respond to keystrokes, calculate live CPM/WPM, and show the end summary.

    Attributes (set in __init__ / _reset_game)
    ------------------------------------------
    language      : "en" or "it" – determines which text pool to use.
    best_cpm      : Highest corrected CPM achieved in this session (persists
                    across rounds until the window is closed).
    words         : List of words in the currently active sample sentence.
    cur_idx       : Index into `words` pointing at the word being typed now.
    record        : List of (typed_word, expected_word) tuples, one per
                    submitted word. Used to count mistakes for the summary.
    correct_chars : Running total of characters in correctly typed words
                    (space separators counted too). Used for live CPM.
    timer_on      : True once the countdown is running.
    time_left     : Seconds remaining; counts down from GAME_DURATION to 0.
    used_enter    : True if the user pressed Enter at least once this round.
    last_word     : True after the timer hits 0 – the user can finish typing
                    their current word, then the game ends automatically.
    _placeholder  : True when the entry field shows the grey hint text.
    _in_commit    : Re-entrancy guard – set to True while _commit() runs so
                    that the StringVar write-trace does not fire recursively.
    _after_id     : ID returned by root.after(), kept so we can cancel it on
                    Restart before the scheduled callback fires.
    _trace_id     : ID returned by typed_var.trace_add(). Stored so we can
                    temporarily remove the callback in _set_var_silent().
    """

    def __init__(self, root):
        """Initialise instance state, build the UI, then start a fresh game."""
        self.root = root
        self.root.title("Typing Speed Test")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Session-level state (survives individual rounds).
        self.language   = "en"
        self.best_cpm   = 0

        # Per-round state is initialised properly in _reset_game().
        # We set sentinel values here just to keep the attribute names visible.
        self._after_id  = None
        self._in_commit = False

        self._build_ui()    # Create all widgets.
        self._reset_game()  # Populate them with a fresh game.

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        """Create the three-row layout: stats bar, text display, input field.

        Row 0 – stats bar
            Labels for Corrected CPM, WPM, Time Left, a red "Restart" link,
            and two flag emoji buttons for language selection.

        Row 1 – text display
            A read-only tk.Text widget that shows the sample sentence. Words
            are coloured dynamically via named tags (see tag_configure calls).

        Row 2 – typing input
            A single-line tk.Entry widget. A StringVar trace fires _on_change
            on every keystroke; <space> and <Return> have dedicated bindings.
        """

        # ── Row 0: stats bar ──────────────────────────────────────────────────
        sf = tk.Frame(self.root, bg=BG, pady=6)
        sf.grid(row=0, column=0, sticky="ew", padx=10)

        # "Your best: N" appears here after the first completed round.
        self.best_var = tk.StringVar(value="")
        tk.Label(sf, textvariable=self.best_var, bg=BG, font=F_STATS).pack(side="left")

        # Live Corrected CPM counter (only correctly typed characters count).
        tk.Label(sf, text="Corrected CPM:", bg=BG, font=F_STATS).pack(side="left", padx=(8, 0))
        self.cpm_var = tk.StringVar(value="?")
        tk.Label(sf, textvariable=self.cpm_var, width=5, bg=BG, font=F_STATS).pack(side="left")

        # Live WPM counter (derived from CPM: WPM = CPM / 5).
        tk.Label(sf, text="WPM:", bg=BG, font=F_STATS).pack(side="left", padx=(8, 0))
        self.wpm_var = tk.StringVar(value="?")
        tk.Label(sf, textvariable=self.wpm_var, width=5, bg=BG, font=F_STATS).pack(side="left")

        # Countdown timer; changes to "Last word" when it reaches 0.
        tk.Label(sf, text="Time left:", bg=BG, font=F_STATS).pack(side="left", padx=(8, 0))
        self.time_var = tk.StringVar(value=str(GAME_DURATION))
        tk.Label(sf, textvariable=self.time_var, width=10, bg=BG, font=F_STATS, anchor="w").pack(side="left")

        # "Restart" is a Label styled as a hyperlink (red, underlined, pointer cursor).
        # It binds a left-click directly to _reset_game instead of using a Button
        # so we avoid the default Button border/relief style.
        lnk = tk.Label(sf, text="Restart", fg="#cc0000", cursor="hand2", bg=BG,
                        font=(F_STATS[0], F_STATS[1], "underline"))
        lnk.pack(side="left", padx=(10, 0))
        lnk.bind("<Button-1>", lambda _: self._reset_game())

        # Language flags – clicking switches the text pool and resets the round.
        # The flag characters are Unicode regional indicator sequences (emoji flags).
        flag_en = tk.Label(sf, text="\U0001f1ec\U0001f1e7", cursor="hand2", bg=BG, font=("Helvetica", 16))
        flag_en.pack(side="left", padx=(14, 2))
        flag_en.bind("<Button-1>", lambda _: self._set_language("en"))

        flag_it = tk.Label(sf, text="\U0001f1ee\U0001f1f9", cursor="hand2", bg=BG, font=("Helvetica", 16))
        flag_it.pack(side="left", padx=2)
        flag_it.bind("<Button-1>", lambda _: self._set_language("it"))

        # ── Row 1: text display ───────────────────────────────────────────────
        tf = tk.Frame(self.root, bg=WHITE, bd=1, relief="solid")
        tf.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))

        # tk.Text is used (instead of a Label) because it supports named colour
        # tags that let us highlight individual words without re-rendering everything.
        # The scrollbar is linked via yscrollcommand / command so they stay in sync.
        self.tw = tk.Text(tf, wrap="word", height=10, width=52, font=F_TEXT,
                          bg=WHITE, relief="flat", state="disabled", cursor="arrow",
                          padx=14, pady=10)
        self._scrollbar = tk.Scrollbar(tf, orient="vertical", command=self.tw.yview)
        self.tw.configure(yscrollcommand=self._scrollbar.set)
        # Pack the scrollbar first on the right so it fills the full height of tf,
        # then pack the text widget to fill the remaining space.
        self._scrollbar.pack(side="right", fill="y")
        self.tw.pack(side="left", fill="both", expand=True)

        # Colour tags used while the game is active:
        self.tw.tag_configure("cur_ok",  background=GRN_BG, foreground="black")  # current word, input matches so far
        self.tw.tag_configure("cur_err", background=RED_BG, foreground="black")  # current word, input does NOT match
        self.tw.tag_configure("ok",      foreground=GRN_FG)  # already submitted, correct
        self.tw.tag_configure("err",     foreground=RED_FG)  # already submitted, wrong
        self.tw.tag_configure("plain",   foreground="black")  # upcoming words (not yet reached)

        # ── Row 2: typing input ───────────────────────────────────────────────
        inf = tk.Frame(self.root, bg=INPUT_BG, bd=1, relief="solid")
        inf.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        # typed_var is the data model for the entry widget.
        # We attach a write-trace so _on_change fires on every character typed.
        # We store the trace ID so we can temporarily remove it in _set_var_silent().
        self.typed_var = tk.StringVar()
        self._trace_id = self.typed_var.trace_add("write", self._on_change)

        self.entry = tk.Entry(inf, textvariable=self.typed_var, font=F_INPUT, bg=INPUT_BG,
                              relief="flat", justify="center", insertbackground="black",
                              disabledbackground=INPUT_BG)
        self.entry.pack(fill="both", expand=True, ipady=10, padx=10)

        # <space> is handled separately because we intercept it to commit the
        # current word and return "break" so the space never enters the field.
        self.entry.bind("<Return>",   self._on_enter)
        self.entry.bind("<space>",    self._on_space)
        self.entry.bind("<FocusIn>",  self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)

        # Allow the single column to stretch horizontally with the window.
        self.root.columnconfigure(0, weight=1)

    # ── Game reset ────────────────────────────────────────────────────────────

    def _reset_game(self):
        """Reset all per-round state and reinitialise the UI for a new game.

        This is called both at startup and whenever the user clicks Restart
        or switches language. It cancels any running timer to avoid two
        parallel countdowns after a mid-game restart.
        """
        # Cancel the pending _tick() callback if the timer was already running.
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

        # Pick a random sentence from the active language pool and split it
        # into a list of words that the player must type one by one.
        texts = TEXTS_EN if self.language == "en" else TEXTS_IT
        self.words         = random.choice(texts).split()

        # Index of the word the player is currently typing.
        self.cur_idx       = 0

        # History of all submitted words as (typed, expected) pairs.
        self.record        = []

        # Accumulator for characters in correctly typed words (used for CPM).
        self.correct_chars = 0

        # Game-flow flags.
        self.timer_on      = False
        self.time_left     = GAME_DURATION
        self.used_enter    = False  # True if Enter was pressed at least once.
        self.last_word     = False  # True once the timer has expired.
        self._placeholder  = False
        self._in_commit    = False

        # Reset the displayed stats.
        self.cpm_var.set("?")
        self.wpm_var.set("?")
        self.time_var.set(str(GAME_DURATION))

        # Restore the text widget's font/padding in case it was changed by
        # _render_summary() at the end of a previous round.
        self.tw.config(state="normal", font=F_TEXT, padx=14, pady=10)
        self.tw.config(state="disabled")
        self._render_text("")

        # Re-enable the entry field and show the placeholder hint.
        self.entry.config(state="normal")
        self._set_placeholder()
        self.entry.focus_set()

    def _set_language(self, lang):
        """Switch the active language and start a fresh round."""
        self.language = lang
        self._reset_game()

    # ── Placeholder helpers ───────────────────────────────────────────────────

    def _set_placeholder(self):
        """Show grey hint text in the entry field when it is empty and unfocused."""
        self._placeholder = True
        ph = "type the words here" if self.language == "en" else "digita le parole qui"
        self.entry.config(fg=PH_FG)
        # Use _set_var_silent so the write-trace doesn't fire for placeholder text.
        self._set_var_silent(ph)

    def _clear_placeholder(self):
        """Remove the grey hint text so the user can start typing real input."""
        if self._placeholder:
            self._placeholder = False
            self.entry.config(fg="black")
            self._set_var_silent("")

    def _set_var_silent(self, value):
        """Set typed_var to `value` without triggering the _on_change callback.

        Normally, any write to typed_var fires the trace we registered in
        _build_ui(). When we programmatically clear the field (after committing
        a word, restoring the placeholder, etc.) we don't want _on_change to
        run, so we temporarily remove the trace, set the value, then re-attach.
        """
        self.typed_var.trace_remove("write", self._trace_id)
        self.typed_var.set(value)
        self._trace_id = self.typed_var.trace_add("write", self._on_change)

    def _focus_in(self, _=None):
        """Called when the entry gains focus – clears placeholder if present."""
        self._clear_placeholder()

    def _focus_out(self, _=None):
        """Called when the entry loses focus – restores placeholder if empty
        and the game hasn't started yet."""
        if (not self._placeholder and not self.typed_var.get().strip()
                and self.cur_idx == 0 and not self.timer_on):
            self._set_placeholder()

    # ── Text display ──────────────────────────────────────────────────────────

    def _render_text(self, current_typed):
        """Redraw the sample sentence in the text widget with colour highlights.

        This is called on every keystroke and after every committed word.
        It redraws the whole sentence from scratch each time, which is fast
        enough for sentences of this length.

        Colour logic
        ------------
        - Already submitted, correct  → green foreground ("ok" tag).
        - Already submitted, wrong    → red foreground ("err" tag).
        - Current word, input matches → green background ("cur_ok" tag).
        - Current word, no match      → red background ("cur_err" tag).
        - Upcoming words              → plain black ("plain" tag).

        Parameters
        ----------
        current_typed : str
            Whatever the user has typed so far for the current word
            (empty string when between words).
        """
        # We must temporarily re-enable the widget to modify its content.
        self.tw.config(state="normal")
        self.tw.delete("1.0", "end")

        for i, word in enumerate(self.words):
            # Add a plain space separator before every word except the first.
            if i:
                self.tw.insert("end", " ", "plain")

            if i < self.cur_idx:
                # This word has already been submitted; colour it by correctness.
                typed, exp = self.record[i]
                self.tw.insert("end", word, "ok" if typed == exp else "err")

            elif i == self.cur_idx:
                # This is the word the user is currently typing.
                # Show a green background if input matches the word's prefix,
                # red if any character diverges.
                tag = "cur_ok" if (not current_typed or word.startswith(current_typed)) else "cur_err"
                self.tw.insert("end", word, tag)

            else:
                # Future words – no colour yet.
                self.tw.insert("end", word, "plain")

        # Lock the widget again so the user can't click and edit it.
        self.tw.config(state="disabled")

    # ── Summary ───────────────────────────────────────────────────────────────

    def _render_summary(self, cpm_raw, cpm_corr, wpm_corr):
        """Replace the text panel content with the end-of-game statistics.

        We reuse the same tk.Text widget rather than creating a new one,
        which avoids any layout shift. We reconfigure its font and padding
        here to suit the smaller summary text size.

        Parameters
        ----------
        cpm_raw  : int  – Total CPM including mistakes (for context).
        cpm_corr : int  – Corrected CPM (only correctly typed words counted).
        wpm_corr : int  – Corrected WPM (= cpm_corr / 5).
        """
        # Switch to the smaller font used in the summary view.
        self.tw.config(state="normal", font=("Helvetica", 13), padx=20, pady=14)
        self.tw.delete("1.0", "end")

        # Define tags for the summary layout.
        self.tw.tag_configure("h",    font=F_SUM_H, justify="center", spacing1=8, spacing3=6)
        self.tw.tag_configure("body", font=F_SUM,   justify="center", spacing1=4)
        self.tw.tag_configure("item", font=F_SUM,   lmargin1=60, lmargin2=60, spacing1=2)
        self.tw.tag_configure("warn", font=F_SUM_W, foreground="#cc6600", justify="center", spacing1=8)

        # Headline score.
        self.tw.insert("end", f"Your score: {cpm_corr} CPM  (that is {wpm_corr} WPM)\n", "h")

        # Filter the record for mistakes only.
        mistakes = [(t, e) for t, e in self.record if t != e]
        n_m = len(mistakes)
        n_w = len(self.record)

        if n_m:
            # Explain the difference between raw and corrected CPM.
            s = "s" if n_m != 1 else ""
            self.tw.insert("end",
                f"\nIn reality, you typed {cpm_raw} CPM, but you made {n_m} mistake{s} "
                f"(out of {n_w} words), which were not counted in the corrected score.\n", "body")

            # List every mistake as a bullet point.
            self.tw.insert("end", "\nYour mistakes were:\n", "body")
            for typed, expected in mistakes:
                self.tw.insert("end", f'  * Instead of "{expected}", you typed "{typed}".\n', "item")
        else:
            self.tw.insert("end", "\nPerfect! No mistakes at all!\n", "body")

        # Extra tip if the player pressed Enter during the round.
        if self.used_enter:
            self.tw.insert("end",
                "\nBy the way, you used Enter instead of the space bar. "
                "Try using space next time; this will probably result in a "
                "greater overall typing speed.\n", "warn")

        self.tw.config(state="disabled")

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _start_timer(self):
        """Start the countdown. Called once on the first real keystroke."""
        self.timer_on = True
        self._tick()

    def _tick(self):
        """Decrement the timer by one second and schedule the next tick.

        Tkinter is single-threaded; root.after() is the correct way to
        implement a recurring callback without blocking the event loop.
        Each call schedules itself to run again 1 000 ms later, creating
        a chain that continues until time_left reaches 0.

        When time_left hits 0 the label changes to "Last word" and
        self.last_word is set to True. The next space the user presses
        will call _commit(), which then calls _finish() because last_word
        is True – ending the game after the current word is submitted.
        """
        if self.time_left > 0:
            self.time_left -= 1
            if self.time_left == 0:
                # Signal the "last word" phase instead of just stopping.
                self.time_var.set("Last word")
                self.last_word = True
            else:
                self.time_var.set(str(self.time_left))
            # Schedule the next tick; store the ID so we can cancel on restart.
            self._after_id = self.root.after(1000, self._tick)

    def _update_live_score(self):
        """Recalculate and display CPM and WPM based on elapsed time.

        CPM formula: (correct chars typed so far) / (elapsed seconds) * 60
        WPM formula: CPM / 5  (industry standard: 1 word ≈ 5 characters)

        We guard against elapsed == 0 to prevent division by zero on the
        very first tick before a full second has passed.
        """
        elapsed = GAME_DURATION - self.time_left
        if elapsed <= 0:
            return
        cpm = round(self.correct_chars / elapsed * 60)
        self.cpm_var.set(str(cpm))
        self.wpm_var.set(str(round(cpm / 5)))

    # ── Key handlers ──────────────────────────────────────────────────────────

    def _on_change(self, *_):
        """Fired by the StringVar write-trace on every character typed.

        Responsibilities:
        1. Ignore the call if the field holds placeholder text or if we're
           inside _commit() (re-entrancy guard via _in_commit).
        2. Start the timer on the very first real keystroke.
        3. Trigger the "too many characters" popup if the user is typing far
           beyond the expected word length (likely forgot to press space).
        4. Redraw the text display with the current input highlighted.
        5. Update the live CPM/WPM counters.

        The *_ parameter absorbs the three arguments Tkinter passes to every
        variable trace (name, index, operation) which we don't need here.
        """
        # Skip silently if the entry is showing placeholder text or if
        # a word commit is already in progress.
        if self._placeholder or self._in_commit:
            return

        typed = self.typed_var.get()

        # Empty field (e.g. just after committing a word) – redraw and stop.
        if not typed:
            self._render_text("")
            return

        # Start the countdown on the first real character.
        if not self.timer_on:
            self._start_timer()

        # Get the word the user is supposed to be typing right now.
        word = self.words[self.cur_idx] if self.cur_idx < len(self.words) else ""

        # If the user has typed more than 10 characters past the expected word
        # length, they probably forgot to press space. Show a warning and restart.
        if len(typed) > len(word) + 10:
            self._too_long_popup(word, len(typed))
            return

        # Update the highlighted text and live score displays.
        self._render_text(typed)
        self._update_live_score()

    def _on_space(self, _):
        """Called when the user presses the space bar.

        Space is the word separator: we read whatever is in the entry,
        commit it as the answer for the current word, and clear the field.

        Returning "break" tells Tkinter to suppress the default key action
        (inserting a literal space character into the entry widget).
        """
        # Do nothing if only placeholder text is showing.
        if self._placeholder:
            return "break"

        typed = self.typed_var.get()
        if typed:
            self._commit(typed)

        return "break"  # Prevent space from appearing in the entry field.

    def _on_enter(self, _):
        """Called when the user presses the Enter/Return key.

        Enter is not a valid word separator in this game (space is).
        We record the event and show a friendly reminder.
        Returning "break" prevents the default action (which would do nothing
        meaningful in an Entry, but we suppress it to be explicit).
        """
        self.used_enter = True
        if self.language == "en":
            msg = "Use the space bar instead of Enter - it's faster!\nUse the Restart link to start over."
        else:
            msg = "Usa la barra spaziatrice invece di Invio - e piu veloce!\nUsa il link Riavvia per ricominciare."
        messagebox.showwarning("Use Space Bar", msg)
        return "break"

    # ── Word commit ───────────────────────────────────────────────────────────

    def _commit(self, typed):
        """Record the typed word and advance to the next one.

        This is the core of the game loop. Each call:
        1. Stores (typed, expected) in self.record for the final summary.
        2. Adds to self.correct_chars if the word was typed perfectly.
        3. Advances self.cur_idx to the next word.
        4. Clears the entry field via _set_var_silent (no trace callback).
        5. Redraws the text and updates the live score.
        6. Ends the game if all words are done or last_word is True.

        The _in_commit flag prevents _on_change from running while we are
        modifying the StringVar internally, which would cause double renders.

        Parameters
        ----------
        typed : str  The text the user had in the entry when they pressed space.
        """
        if self.cur_idx >= len(self.words):
            return  # Safety guard: no more words to commit.

        # Set guard so the trace callback ignores our internal StringVar writes.
        self._in_commit = True

        expected = self.words[self.cur_idx]
        self.record.append((typed, expected))

        # +1 accounts for the space separator between words when calculating CPM.
        if typed == expected:
            self.correct_chars += len(typed) + 1

        self.cur_idx += 1
        self._set_var_silent("")  # Clear the input field without firing the trace.
        self._render_text("")     # Redraw: the just-committed word is now coloured.
        self._update_live_score()

        # Lower the guard before any further logic so state is consistent.
        self._in_commit = False

        # End the game if we've reached the last word, or the timer has expired
        # and the player has now finished their last pending word.
        if self.cur_idx >= len(self.words) or self.last_word:
            self._finish()

    def _too_long_popup(self, word, n):
        """Show a warning popup when the user has typed far too many characters.

        This fires when len(typed) > len(expected_word) + 10, which strongly
        suggests the user forgot to press space between words.
        After the user dismisses the dialog, the round is restarted.

        Parameters
        ----------
        word : str  The expected word (shown in the message).
        n    : int  How many characters the user has typed so far.
        """
        if self.language == "en":
            msg = (f'Er... The word "{word}" is not {n} characters long ... :).\n'
                   "Don't forget to press the space bar after each word!\n"
                   "(You have to start over now...)")
        else:
            msg = (f'Ehm... La parola "{word}" non e lunga {n} caratteri ... :).\n'
                   "Non dimenticare di premere la barra spaziatrice dopo ogni parola!\n"
                   "(Devi ricominciare...)")
        messagebox.showwarning("Too many characters!", msg)
        self._reset_game()

    # ── Game over ─────────────────────────────────────────────────────────────

    def _finish(self):
        """Stop the game, compute final scores, and show the summary screen.

        Called when either:
        - The player has typed all words in the sentence, OR
        - The timer expired (last_word is True) and the player submitted their
          last in-progress word.

        Score calculation
        -----------------
        elapsed  = seconds actually spent typing (capped at 1 to avoid / 0)
        cpm_raw  = all typed characters per minute (includes mistakes)
        cpm_corr = only correctly typed characters per minute
        wpm_corr = cpm_corr / 5  (standard WPM approximation)

        The best_cpm is updated if this round beats the session high score.
        """
        # Cancel any remaining timer callbacks.
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

        self.timer_on = False
        self.entry.config(state="disabled")  # Prevent further input.

        # Time elapsed during this round.  max(1, …) prevents division by zero
        # if the game ends in less than one second (e.g. after typing all words
        # in a very short sentence before the first tick).
        elapsed  = max(1, GAME_DURATION - self.time_left)

        # Sum total chars typed (all words) vs only correct words.
        # +1 per word to count the space separator the player pressed.
        total_c  = sum(len(t) + 1 for t, _ in self.record)
        corr_c   = sum(len(t) + 1 for t, e in self.record if t == e)

        cpm_raw  = round(total_c  / elapsed * 60)
        cpm_corr = round(corr_c   / elapsed * 60)
        wpm_corr = round(cpm_corr / 5)

        # Update session best and display it in the stats bar.
        if cpm_corr > self.best_cpm:
            self.best_cpm = cpm_corr
        self.best_var.set(f"Your best: {self.best_cpm}")

        # Freeze the stats bar at the final values.
        self.cpm_var.set(str(cpm_corr))
        self.wpm_var.set(str(wpm_corr))
        self.time_var.set("0")

        # Replace the sample-text panel with the summary.
        self._render_summary(cpm_raw, cpm_corr, wpm_corr)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    """Create the Tkinter root window and start the application event loop."""
    root = tk.Tk()
    TypingSpeedTest(root)
    root.mainloop()  # Blocks until the window is closed.


if __name__ == "__main__":
    main()
