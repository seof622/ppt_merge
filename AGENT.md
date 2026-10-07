# AGENTS.md

## Project Overview

Build a Windows desktop application that combines slides from multiple existing PowerPoint files into a new PowerPoint presentation.

The user should be able to:

1. Add multiple `.pptx` / `.pptm` files
2. Browse slide thumbnails
3. Select slides from any source presentation
4. Add them to an output sequence
5. Reorder them with drag and drop
6. Generate a new `.pptx` in the selected order

The highest-priority requirement is:

> Preserve the original PowerPoint slide as faithfully as possible.

Do not rebuild slide contents element-by-element.

Use Microsoft PowerPoint itself through COM Automation to copy or insert slides.

---

# Tech Stack

Use:

- Python 3.12+
- PySide6
- pywin32
- pythoncom
- Microsoft PowerPoint COM Automation
- Windows 10 / 11

Microsoft PowerPoint must be installed on the target machine.

Do not use `python-pptx` as the main slide-copying engine.

`python-pptx` may only be used for optional metadata inspection if necessary.

---

# Core Principle

The application must not recreate PowerPoint content such as:

- text
- images
- shapes
- charts
- SmartArt
- tables
- animations
- transitions
- slide masters
- layouts
- themes

Instead, PowerPoint must perform the slide copy operation itself through COM.

Preferred approaches to investigate:

```python
slide.Copy()
destination.Slides.Paste()
```

and:

```text
Slides.InsertFromFile
```

Evaluate which approach preserves slide appearance and behavior more reliably.

---

# Highest Priority Validation

Before implementing the full UI, create a technical proof of concept.

The first milestone must be able to do:

```text
A.pptx / Slide 2
B.pptx / Slide 4
A.pptx / Slide 1

↓

result.pptx
```

Verify preservation of:

- fonts
- images
- SVG
- shapes
- grouped shapes
- charts
- Excel-linked charts
- tables
- SmartArt
- embedded objects
- audio
- video
- slide background
- theme
- layout
- slide master
- animation
- transition
- hyperlinks
- internal slide links
- speaker notes

Do not spend significant time on UI before this validation succeeds.

---

# Architecture

Separate UI code from PowerPoint automation.

Recommended structure:

```text
src/
    main.py

    ui/
        main_window.py
        source_panel.py
        slide_grid.py
        output_panel.py
        slide_item_widget.py

    ppt/
        powerpoint_service.py
        presentation_manager.py
        thumbnail_service.py

    models/
        slide_model.py
        presentation_model.py
        project_model.py

    workers/
        ppt_worker.py

    utils/
        logger.py
        file_utils.py
```

Never manipulate COM objects directly inside PySide6 widgets.

All PowerPoint operations must go through a service layer.

---

# Data Models

Use dataclasses and type hints.

Example:

```python
@dataclass
class SlideItem:
    source_file: str
    source_file_name: str
    slide_index: int
    slide_id: int | None = None
    thumbnail_path: str | None = None
    title: str | None = None
```

Output ordering should be represented as:

```python
list[SlideItem]
```

The same source slide may appear multiple times.

Example:

```text
A.pptx / Slide 1
A.pptx / Slide 3
A.pptx / Slide 1
```

This must be valid.

---

# UI Layout

The main window should contain three major areas.

```text
┌──────────────────────────────────────────────────┐
│ Toolbar                                          │
├───────────────┬──────────────────────────────────┤
│ Source files  │ Slides from selected PPT         │
│               │                                  │
│ A.pptx        │ [1] [2] [3] [4]                 │
│ B.pptx        │ [5] [6] [7] [8]                 │
│ C.pptx        │                                  │
├───────────────┴──────────────────────────────────┤
│ Output slide sequence                            │
│                                                  │
│ [A-1] [B-3] [A-5] [C-2]                        │
├──────────────────────────────────────────────────┤
│                 Generate PPT                     │
└──────────────────────────────────────────────────┘
```

Optimize the UI for desktop productivity rather than visual decoration.

Target primary display size:

```text
1920x1080
```

---

# Source File Panel

Support:

- Add PPT files
- Multi-file selection
- Drag and drop files into the app
- Remove a source file
- Clear all sources

Supported formats:

```text
.pptx
.pptm
```

`.ppt` support may be added later.

Display for each source:

- filename
- slide count
- full path in tooltip

---

# Slide Browser

When a source presentation is selected, display its slides in a thumbnail grid.

Each item should display:

- slide thumbnail
- slide number
- optional title

Support:

- single selection
- Ctrl multi-select
- Shift range selection
- double-click to add
- context menu to add
- drag and drop into output list

---

# Thumbnail Generation

Generate thumbnails through PowerPoint COM.

Prefer:

```text
Slide.Export()
```

Export thumbnails as PNG.

Cache thumbnails.

Recommended cache structure:

```text
cache/
    <presentation_hash>/
        slide_1.png
        slide_2.png
        slide_3.png
```

Use file modification time and/or file hash to detect stale cache entries.

Do not regenerate thumbnails unnecessarily.

For large presentations, consider lazy loading.

---

# Output Slide Sequence

The output panel represents the final PPT order.

Each item should display:

- thumbnail
- source filename
- source slide number

Support:

- drag-and-drop reorder
- multi-selection
- Delete key removal
- context menu removal
- duplicate
- move up
- move down
- move to beginning
- move to end
- clear all

---

# PPT Generation

When the user clicks Generate:

Iterate through the ordered slide list.

Example:

```text
1. A.pptx Slide 3
2. B.pptx Slide 1
3. A.pptx Slide 5
4. C.pptx Slide 2
```

Create a new PowerPoint presentation containing those slides in exactly that order.

The final presentation must preserve source formatting.

---

# Themes and Slide Masters

Different source files may contain different:

- themes
- slide masters
- layouts

Example:

```text
A.pptx → Theme A / Master A
B.pptx → Theme B / Master B
C.pptx → Theme C / Master C
```

The generated presentation should visually preserve each source slide.

Do not automatically normalize all slides to the destination theme.

Preserving source appearance is more important than reducing the number of masters in the output file.

---

# Slide Size

Source presentations may use different slide sizes.

Example:

```text
A.pptx → 16:9
B.pptx → 4:3
```

PowerPoint presentations cannot independently store a different page size for every slide.

Default behavior:

- use the slide size of the first output slide / first source presentation
- detect inconsistent source slide sizes
- show a clear warning before generation

Example message:

```text
Some source presentations use different slide sizes.

A.pptx: 16:9
B.pptx: 4:3

The generated presentation will use the size of the first presentation.
```

Do not silently resize without warning.

---

# PowerPoint COM Management

Prefer creating an application-specific PowerPoint instance:

```python
win32com.client.DispatchEx("PowerPoint.Application")
```

Do not attach to and later terminate a PowerPoint instance the user was already using.

Keep PowerPoint hidden where practical, but prioritize reliability over invisibility.

---

# COM Lifecycle

COM lifecycle management is critical.

The application must not leave orphaned:

```text
POWERPNT.EXE
```

processes after normal completion or errors.

Always close:

- source presentations
- destination presentations

Release references to:

- Slide
- Slides
- Presentation
- Presentations
- Application

Use `try / finally` around COM-heavy operations.

The application must never kill unrelated PowerPoint processes started by the user.

---

# Threading Rules

Long-running PowerPoint work must not freeze the UI.

Move tasks such as:

- opening presentations
- reading slides
- exporting thumbnails
- generating final PPT

to worker threads.

Use PySide6:

```text
QObject
QThread
signals / slots
```

or an appropriate thread-pool approach.

COM apartment rules must be respected.

Every thread performing COM work must call:

```python
pythoncom.CoInitialize()
```

and before exiting:

```python
pythoncom.CoUninitialize()
```

Do not directly share COM objects between threads.

Pass plain Python data between threads instead.

---

# Progress Reporting

Long-running tasks must expose progress.

Examples:

```text
Loading presentation...

A.pptx
Slide 13 / 56
```

and:

```text
Generating PowerPoint...

37 / 120 slides
```

Use signals to update the UI.

---

# Cancellation

Design worker operations so that generation can be cancelled safely.

On cancellation:

- stop at the next safe point
- close all opened presentations
- clean up temporary files if appropriate
- release COM objects
- do not leave `POWERPNT.EXE` running
- handle partially created output files intentionally

---

# Error Handling

Handle at minimum:

## Missing file

Show:

```text
The PowerPoint file could not be found.
```

## PowerPoint not installed

Show:

```text
Microsoft PowerPoint must be installed to use this application.
```

## Corrupted presentation

Show a user-friendly message.

## Password-protected presentation

Detect and report that the file cannot be opened automatically.

## Output file already exists

Ask before overwrite.

## Locked or already-open source

Attempt safe read-only behavior where possible.

Never display raw COM errors directly to users.

Bad:

```text
(-2147352567, 'Exception occurred.', ...)
```

Good:

```text
An error occurred while opening the PowerPoint presentation.

See the application log for details.
```

Log the original COM exception and HRESULT.

---

# Logging

Use Python `logging`.

Do not use `print()` for application diagnostics.

Log:

- app start
- app shutdown
- source PPT open
- source PPT close
- thumbnail export
- slide copy
- slide paste
- destination save
- COM exceptions
- HRESULT values
- unexpected exceptions

Recommended path:

```text
logs/app.log
```

---

# Autosave / Recovery

Design the project state so it can be serialized.

Persist at least:

```text
source file paths
output slide order
```

Example:

```json
{
  "sources": ["C:/ppt/A.pptx", "C:/ppt/B.pptx"],
  "slides": [
    {
      "source": "C:/ppt/A.pptx",
      "slide": 3
    },
    {
      "source": "C:/ppt/B.pptx",
      "slide": 1
    }
  ]
}
```

Full recovery UI can be implemented after MVP.

---

# Project File

Design with future support for a project file such as:

```text
example.pptcomposer
```

The file may internally contain JSON.

Project persistence is not required for the initial MVP, but the model layer should make it easy to add later.

---

# Performance Expectations

Typical target:

```text
10–20 source PPT files
100–500 total slides
```

The UI should remain responsive with several hundred thumbnails.

Use:

- thumbnail caching
- lazy loading where appropriate
- worker threads

Avoid opening and closing the same PowerPoint file repeatedly if a safer reuse strategy is available.

---

# MVP Scope

Implement these features first:

1. Add PowerPoint files
2. Display source file list
3. Read slide count
4. Export slide thumbnails
5. Display thumbnail grid
6. Select slides
7. Add slides to output list
8. Reorder output slides by drag and drop
9. Remove slides from output
10. Generate new PowerPoint
11. Preserve source formatting
12. Choose output path
13. Report progress
14. Handle COM errors
15. Cleanly terminate the app-owned PowerPoint process

Do not prioritize advanced features until the MVP is stable.

---

# Post-MVP Features

Possible future features:

- save project
- open project
- recent projects
- Undo / Redo
- slide search
- title search
- favorites
- templates / presets
- duplicate detection
- automatic categorization
- dark mode
- multiple projects
- update mechanism
- slide grouping
- output section dividers

Do not implement these unless requested.

---

# Testing

Create representative PowerPoint test files.

## Basic

```text
test_basic.pptx
```

Contains:

- text
- images
- shapes

## Charts

```text
test_chart.pptx
```

Contains:

- native PowerPoint charts
- Excel-linked charts

## Animations

```text
test_animation.pptx
```

Contains:

- entrance animation
- motion animation
- transition

## Masters

```text
test_master.pptx
```

Contains:

- custom slide master
- custom layouts
- theme colors

## Media

```text
test_media.pptx
```

Contains:

- video
- audio

## SmartArt

```text
test_smartart.pptx
```

## Mixed Themes

```text
test_theme_a.pptx
test_theme_b.pptx
```

Combine these presentations and manually compare the generated output against the originals.

---

# Mandatory Reliability Tests

Test these scenarios:

## Test 1

Add 10 PPT files and exit.

Expected:

```text
No orphan POWERPNT.EXE process
```

## Test 2

Generate a presentation and cancel midway.

Expected:

```text
Presentations closed
COM references released
No orphan PowerPoint instance
```

## Test 3

One source PPT fails to open.

Expected:

```text
Failure is isolated
Other source files remain usable
```

## Test 4

Generation throws an exception.

Expected:

```text
COM cleanup still occurs
partial output is handled safely
```

## Test 5

PowerPoint is already open before this application starts.

Expected:

```text
Closing this application must not terminate the user's existing PowerPoint session
```

---

# Coding Standards

Use:

- Python type hints
- dataclasses for models
- clear separation of concerns
- small focused modules
- explicit exception handling
- descriptive names

Avoid:

- giant `main.py`
- business logic inside UI widgets
- global COM objects
- raw COM exceptions in UI
- direct cross-thread COM object access
- unnecessary abstraction before functionality is proven

---

# Development Order

Follow this order.

## Phase 1 — COM Proof of Concept

Create a small script that combines specific slides from multiple presentations into a new PowerPoint file.

Do not create the full UI yet.

Validate slide fidelity.

## Phase 2 — Thumbnail Engine

Implement PowerPoint-based thumbnail exporting and caching.

## Phase 3 — Basic PySide6 UI

Implement:

- source file list
- selected presentation slide grid

## Phase 4 — Output Composer

Implement:

- add slides
- remove slides
- drag and drop ordering

## Phase 5 — Generation Integration

Connect the ordered model to the COM generation engine.

## Phase 6 — Reliability

Focus heavily on:

- COM cleanup
- threading
- cancellation
- error handling
- logging

## Phase 7 — UX Polish

Only after core PPT preservation and reliability are verified.

---

# Decision Priority

When tradeoffs occur, use this priority order:

```text
1. Source slide fidelity
2. Data safety
3. COM reliability
4. Correct slide ordering
5. UI responsiveness
6. User convenience
7. Visual polish
```

Do not sacrifice slide fidelity for implementation convenience.

---

# Definition of Done

The MVP is considered complete when a user can:

```text
1. Drag multiple PPT files into the application
2. Browse slide thumbnails
3. Select slides from different presentations
4. Add them to an output sequence
5. Reorder them
6. Click Generate
7. Save a new PPTX
```

and the generated slides appear and behave as closely as possible to their respective source slides, including source-specific formatting, themes, layouts, animations, transitions, charts, media, and notes.

The application must also exit without leaving behind an application-owned PowerPoint process.

## Communication Language

- Always communicate with the user in Korean.
- All explanations, progress updates, summaries, and questions must be written in Korean.
- Code, identifiers, filenames, API names, library names, and technical terms may remain in English where appropriate.
- Code comments should preferably be written in Korean unless English is more natural or required by the project.
- Do not switch to English unless the user explicitly requests it.
