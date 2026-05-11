# Project Retrospective — Image Watermark Tool

**Author:** Antonio Di Felice  
**Date:** April 2026  
**Platform:** Desktop — Python / Tkinter / Pillow (Windows/macOS/Linux)

---

## Project Overview

A desktop GUI application that overlays a transparent PNG watermark onto any user-selected image and
saves the result. The user uploads an image, selects one of five watermark positions from a dropdown,
and downloads the composited output — all without opening an image editor.

**Tech stack:** Python · Tkinter · Pillow (PIL) · `pathlib` · `filedialog`  
**Architecture:** Procedural GUI with a pure-function image processing core (`watermark_with_transparency`) decoupled from the Tkinter event layer.

---

## Part 1 — Design and Prototyping

### Challenge: Figma without prior experience

The first obstacle was producing a concrete UI prototype. Having limited experience with Figma,
creating the layout from scratch proved time-consuming. The solution was to use **Figma Make**, the
platform's AI-assisted generation feature, with a descriptive prompt:

> *"A watermarking application styled as a classic Tkinter desktop interface — Windows 98 aesthetic,
> grey bevelled borders, blue title bar, classic desktop controls. Features: image upload, watermark
> text customisation (position, font size, opacity), download."*

Figma generated a fully-fledged mockup including features outside the project scope. The iteration
was then to strip it back to only what was needed — upload, position selector, download, clear — which
produced the `prototype.png` used as the definitive layout contract.

**Lesson:** AI-assisted design tools are most effective when given a narrow, well-scoped prompt.
Starting broad and pruning is faster than starting narrow and expanding, because the generator fills
in aesthetic details (colours, spacing, typography) that are expensive to invent but cheap to discard.

---

### Challenge: Tkinter frame-based layout

Tkinter's grid and pack geometry managers are expressive but their interaction with nested
`LabelFrame` / `Frame` containers is not intuitive. Without prior exposure to complex Tkinter layouts,
building the three-section UI (upload panel, position panel, action buttons) from documentation alone
was slow.

The resolution was to use the prototype image directly as a reference for AI-assisted code generation
of the layout skeleton. The generated code correctly used `LabelFrame` with `GROOVE` relief for the
two grouped sections, `columnconfigure(weight=1)` to allow horizontal stretching, and `sticky="ew"`
on every child widget to fill available width consistently.

**Lesson:** For GUI scaffolding tasks, a visual prototype handed to an AI code generator is more
precise than a text description — the image encodes alignment, grouping, and proportion information
that is tedious to express in words and easy to misinterpret.

---

## Part 2 — Implementation Challenges

### Challenge 1: Pillow `paste()` API — string vs. coordinate tuple

The most concrete bug in the project arose when integrating the watermarking logic. The initial call
passed the position as a string:

```python
# WRONG — PIL's paste() expects (x, y), not a label string
transparent.paste(watermark, "Bottom Right", mask=watermark)
```

Pillow's `Image.paste()` accepts an `(x, y)` integer tuple for the top-left corner of the pasted
image — it has no awareness of named positions. Passing a string raised a `TypeError` at runtime.

**Resolution:** The position string is resolved to pixel coordinates **before** the paste call, using
the base image dimensions and watermark dimensions to calculate the correct offset for each of the
five supported positions:

```python
width, height = base_image.size

if position == "Bottom Right":
    position = (width - watermark.width - 10, height - watermark.height - 10)
elif position == "Bottom Left":
    position = (10, height - watermark.height - 10)
elif position == "Top Right":
    position = (width - watermark.width - 10, 10)
elif position == "Top Left":
    position = (10, 10)
elif position == "Center":
    position = ((width - watermark.width) // 2, (height - watermark.height) // 2)
```

The 10-pixel margin keeps the watermark off the image edge regardless of image size.

**Lesson:** Library functions that accept coordinates as positional arguments are a common source of
type errors when the calling code uses human-readable labels internally. Resolve semantic labels to
concrete types at the boundary — before any library call — keeping the library-facing code simple and
the mapping logic in one explicit place.

---

### Challenge 2: RGBA compositing — transparency-correct watermarking

A naive approach to overlaying a PNG watermark is to paste it directly onto a JPEG base image.
This fails when the watermark has a transparent background: JPEG has no alpha channel, so any
transparency in the watermark becomes solid black.

The correct approach creates a **full-size transparent RGBA canvas** as an intermediate layer:

```python
# 1. Create a transparent canvas the same size as the base image
transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))

# 2. Paste the base image onto the canvas (no transparency needed here)
transparent.paste(base_image, (0, 0))

# 3. Paste the watermark using its own alpha channel as a mask
transparent.paste(watermark, position, mask=watermark)

# 4. Save the composited result
transparent.save(output_image_path)
```

The `mask=watermark` argument tells Pillow to use the watermark's alpha channel as a blending mask:
transparent watermark pixels become fully transparent in the output, semi-transparent pixels blend
proportionally, and opaque pixels fully cover the base image.

**Lesson:** Image compositing requires awareness of colour mode (RGB vs RGBA). Always use an RGBA
intermediate when combining images with transparency, and always pass the source image's alpha channel
as the mask to `paste()` — without the mask argument, transparent areas are rendered as solid black.

---

### Challenge 3: UI state management — progressive disclosure

The Download button is meaningless before an image has been loaded. Leaving it enabled invites
errors; showing a dialog that then fails to produce output degrades user trust.

The solution applies the **progressive disclosure** principle: the button starts `DISABLED` and is
only enabled inside `upload_file()` after a valid path has been selected:

```python
def upload_file():
    path = filedialog.askopenfilename(...)
    if path:
        input_path_var.set(path)
        btn_download.config(state=NORMAL)   # Enable only on success
        set_status(f"Loaded: {os.path.basename(path)}")
```

The `Clear` button resets the button state to `DISABLED` again, making the transition reversible.

**Lesson:** Disabling actions until their preconditions are met is cheaper than validating at action
time and showing error dialogs. It also makes the application state self-documenting — the button
state itself communicates what step the user should take next.

---

## Part 3 — Architecture Decisions

### Pure function for image processing

The `watermark_with_transparency()` function takes four arguments (input path, output path, watermark
path, position string) and produces no return value — its only side effect is writing a file. It has
no dependency on any Tkinter widget or global GUI state.

This separation means:
- The watermarking logic can be tested independently of the GUI by calling the function directly.
- The function is reusable in a batch-processing script, a web endpoint, or a CLI tool without
  modification.
- The GUI layer acts as a thin adapter: collect paths from file dialogs, resolve the position string,
  call the function, update the status bar.

### Centralised path construction with `pathlib`

The watermark asset path is resolved at module load time using `pathlib.Path`:

```python
BASE_DIR = Path(__file__).parent
WATERMARK_IMAGE_PATH = BASE_DIR / "assets" / "watermark.png"
```

This construction is platform-agnostic (no hardcoded `\` vs `/` separators) and relative to the
script's location, so the application works correctly regardless of the working directory from which
it is launched.

---

## Part 4 — Lessons Learned Summary

| Area | Lesson |
|---|---|
| **AI-assisted prototyping** | Use AI design tools with a broad prompt, then prune — generating excess features is faster than iterating on an under-specified design. |
| **GUI scaffolding** | A visual prototype image is a more precise spec for layout generation than a text description. Encode alignment and grouping visually. |
| **Library API boundaries** | Resolve semantic types (strings, enums) to the types a library expects (tuples, integers) at the call site boundary. Never pass labels where coordinates are expected. |
| **Image compositing** | Use an RGBA intermediate canvas for transparency-correct compositing. Always pass the source's alpha channel as `mask` to `paste()`. |
| **UI state management** | Disable actions until preconditions are met (progressive disclosure). This is simpler and friendlier than runtime validation dialogs. |
| **Path handling** | Use `pathlib.Path(__file__).parent` for all asset paths. Hardcoded string paths break when the working directory changes. |

---

## Part 5 — Skills Demonstrated

- **Pillow / image processing:** RGBA compositing, alpha-channel masking, multi-format file I/O, coordinate-space arithmetic for dynamic watermark placement.
- **Tkinter GUI development:** `LabelFrame` / `Frame` grid layout, `StringVar` state binding, `ttk.Combobox`, `filedialog` integration, widget state management (`NORMAL` / `DISABLED`).
- **Software design:** pure-function core decoupled from UI, progressive disclosure pattern, cross-platform path handling with `pathlib`.
- **Debugging:** identifying API type mismatches (`str` passed where `tuple` expected), resolving PIL transparency compositing issues.
- **AI-assisted workflow:** using AI tools for prototype generation and layout scaffolding, then refining and integrating the output into production code.
