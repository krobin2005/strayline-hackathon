# Live demo with Wi-Fi off

Everything works offline once `setup.sh` has run.

## Quick start: one double-click

Turn Wi-Fi off, quit Chrome, ChatGPT and Claude, then double-click **`start_demo.command`** in the repo (on Kyle's laptop there's also `Start Strayline Demo.command` on the Desktop). From Terminal: `./start_demo.command`.

It checks Wi-Fi and memory-hungry apps, starts Ollama, builds the logs file if needed, starts the app offline, waits until both models are loaded (about a minute), then opens Safari and the folder of demo files. Keep its Terminal window open during the demo; Ctrl+C or closing the window stops the app. If a step fails it says why, such as an old copy of the app still holding port 8000.

The manual steps below do the same thing, if you'd rather run them one by one.

## Before you start

Turn Wi-Fi off. Quit Chrome, ChatGPT, Claude and anything else heavy: both models together need about 13.4 GB of free memory, and with those apps open Ollama keeps only one model loaded, so switching inputs costs a 20–50 s reload.

## Terminal, tab 1

Start Ollama and go to the project:

```bash
open -a Ollama
```

```bash
cd ~/Projects/strayline-hackathon
```

Make sure the logs demo file exists (builds it in about 10 s if it's missing; no internet needed):

```bash
ls data/demo/campus_afternoon.csv || .venv/bin/python tests/make_demo_intrusions.py
```

Start the app and leave this tab running:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m desk
```

The repeating `GET /api/health 200 OK` lines are the page checking its connection; they are normal. So are the PyTorch "Redirects" note and the "mel filter" warning at start-up.

## Terminal, tab 2 (⌘T), about a minute later

Check both models are loaded. You want `qwen3-vl:8b` and `gemma4:e4b-it-q4_K_M` listed:

```bash
ollama ps
```

Open the app in Safari, and the folder of demo files to drag from:

```bash
open -a Safari http://localhost:8000
```

```bash
open ~/Desktop/"Strayline Demo Files"
```

On a laptop without that Desktop folder, the same files are in the repo:

```bash
open ~/Projects/strayline-hackathon/demo ~/Projects/strayline-hackathon/data/demo
```

## Start the case from the slides (one click)

With the app running (start it before the pitch), the **▶ Run the live case** button on slide 4 opens
`http://localhost:8000/?case=demo`. The page loads the five demo files from this laptop and runs them in
order, exactly as if they had been dragged in. It works with Wi-Fi off, because the address is the laptop itself.
The link needs the app already running: a link can open a page, but not start a program.

To present offline, open the deck in Google Slides while still online with offline access on, or download it
(File → Download → Microsoft PowerPoint) and present it in Keynote or PowerPoint; the link works in all three.

## Run the whole case in the background (recommended)

In the pitch this happens on slide 4 (about 1:20), and you come back to the console after the detector slide (about 3:40); see PLAN.md §6.

Select all five numbered files in the Finder window (⌘A, or drag a box around them) and drag them onto the Strayline page. Drop them anywhere on the page, not just the text box. You can also press ＋ and pick several files.

The page analyses them one after another, in filename order, while you carry on with the slides: video (~60 s), screenshot, voicemail, runbook, then the logs. The whole case takes about 2 minutes. When it says "Case finished", go back to the page and walk through the answers.

Then show it working live: press **Ask about this file** under any file to ask a follow-up, for example on the runbook, "What is Identity Operations' phone number?" ("This isn't in the document"), or on the logs, "What is int-host-5 doing across incidents 2 and 4?". Ask the code question with no file attached.

If something in the box was typed before dropping, every file gets that question instead of its default.

## The demo, one file at a time

The Desktop folder numbers the files in this order. The case (North Hall College, ticket NH-184) is fictional; see `demo/README.md`.

| # | Drag in | Ask | Check on screen |
|---|---|---|---|
| 1 | `1 recovery-review.mp4` (start first; about 60 s) | What was the last action, and when did it happen? | Identity review opened at 14:04; show the sampled frames |
| 2 | `2 recovery-notice.png` | What is the ticket number, and what happened at 14:03? | NH-184; the request was put on hold |
| 3 | `3 callback.wav` | What did the caller report, and what do they want checked? | Open the transcript |
| 4 | `4 runbook.md` | Which group handles this ticket? | Identity Operations, with the passage |
| 5 | `4 runbook.md` | What is its phone number? | "This isn't in the document." |
| 6 | nothing | Write a Python function that counts distinct ticket IDs in a list, and test it on a list with a duplicate. | Ran and passed its tests |
| 7 | `5 campus_afternoon.csv` | Which incident should I look at first? | #1 is the HTTP flood (planted, synthetic) |
| 8 | same file | What is int-host-5 doing across incidents 2 and 4? | Sweep and port scan, then a 1.6 GB upload |

## Optional check

In the morning rather than right before going on, with the app running, this tests every input in about 2 minutes:

```bash
cd ~/Projects/strayline-hackathon && .venv/bin/python tests/smoke_api.py
```

## Stop

Press Ctrl+C in tab 1.

## Phone (optional)

With Wi-Fi off there's no network for the phone. Turn on the phone's hotspot with mobile data off, join it from the laptop, restart the app, and open the "on your phone" address it prints. The mic button is hidden on phones; upload a voice memo instead.
