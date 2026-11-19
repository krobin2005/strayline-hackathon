# Strayline Desk: hackathon plan (v2, after the problem statement)

IEEE AI Hackathon 2026, "Multimodal LLM Challenge". All times ET. 1st place $600, 2nd $300.
Source: the kickoff slides and problem-statement email from Vedanshi Shah, Nov 18. The problem-statement PDF itself is a Northeastern SharePoint link that we haven't opened; the slides cover the same ground.

---

## 1. What the brief actually asks for

> **Build AI we own.** Build a multimodal LLM that runs entirely on your own machine using open-weight models, and use it to solve a real problem for a real user you choose.

- **One interface, five kinds of input, every one shown working live on Day 3:**

  | Input | Must do |
  |---|---|
  | Image | Describe a photo and answer questions about it |
  | Audio | Transcribe speech, answer questions about it, **identify sounds** |
  | Text | Answer questions about a document, and **say so when the answer isn't there** |
  | Code | Write **working** code from a prompt |
  | Video | Describe a short clip and answer questions about it |

- **Constraints:** open-weight models only, running locally (so the local-LLM question is answered: yes). AI coding tools are fine for writing code, not as the system's brain. List our hardware on the slides.
- **Judges reward a specific user with a specific problem** over "anyone could use it."
- **Practice pack** (not scored): kaggle.com/datasets/bhavyasreepylaa/ieee-ai-hackathon-2026-practice-pack: 25 image, 20 audio, 20 text, 20 code, 15 video items.
- **Repo:** our team's **public** repo **in the IEEE GitHub organization**. Our `krobin2005/strayline-hackathon` is temporary; we move the history over when we get the org repo.

### Judging (final round, 0–5 per item, weighted)

| Criterion | Weight | What earns it |
|---|---|---|
| **Multimodal checklist** | **30%** | All five inputs working, **plus our own test results** |
| **Real-world usability** | **25%** | Live demo works start to finish, in a real app that's easy to use |
| **Architecture** | 20% | Explain each model and why we chose it, name our limits, runs well locally |
| **Impact** | 15% | A specific group with a real problem, and **evidence it helps them** |
| **Judges' questions** | 10% | Clear, direct answers |
| *Bonus* | | Works on **web and mobile** |

### Day 3 format

- **Round 1:** a **5-minute** live pitch to two judges, each giving a single 0–5 score. Only the top teams advance.
- **Final:** 15 minutes with all four judges, scored on the full criteria above.
- **Code deadline: Thursday Nov 19, end of day.** Not Friday. Friday is presentations only.

---

## 2. Does Strayline still stand?

**As originally planned: no.** The old plan was a network intrusion detector with an LLM triage layer. It covers **one** of the five inputs (images, via incident charts). That means it would score near zero on the 30% checklist, and the scoring is built around a general multimodal assistant. The ML research parts (catchability map, held-out families, ablation) don't map to any criterion. The code is also due ~24 hours earlier than we planned.

**Reframed: yes, and it's a strong fit.** Keep the name, the user and the "data that can't leave the building" story, and make the five-input assistant the product:

> **Strayline Desk: an offline security assistant for a small college's IT security team.** Two or three people defend thousands of users. Their logs, screenshots, voicemails and incident notes contain student and staff data, so they can't paste them into ChatGPT. Strayline Desk runs on one laptop, offline, and works with everything they handle in a day.

| Input | General ability (for the checklist) | Security job (for the user) |
|---|---|---|
| Image | Describe and answer questions about any photo | Screenshot of a suspicious email or login page: "Is this phishing? What gives it away?" Also reads Strayline's own incident charts |
| Audio | Transcribe, answer questions, identify sounds | A voicemail reported as a scam call: transcript, "what are they asking for?", background sounds |
| Text | Answer from a document, or say it's not there | The college's incident-response runbook and policies: "Who do we notify for a compromised account?" |
| Code | Write working code, checked by running it | "Write a Python function that finds hosts hitting more than 100 ports a minute in this log", then run it on the log |
| Video | Describe a clip and answer questions about it | Screen recording a user sent of a "tech support" pop-up: what happened, step by step |
| **Logs** (our extra) | | **Strayline detector:** a day of connection logs → ranked incidents → open one and ask about it in the same chat |

Why this beats a generic assistant:
- **Impact (15%):** a specific user (small-college IT security), a specific problem (sensitive data that can't go to cloud AI), and a natural reason to be local.
- **Architecture (20%):** the Strayline detector is real ML we can explain. Very few teams will have something like it.
- **Evidence it helps:** Time a teammate completing the sample case and report the result as an internal rehearsal.

**Scope cut from the README spec:** the autoencoder, daily thresholds, the 10-seed catchability map, the investigator agent, the triage ablation and the 2018 cross-network test are all **out**. The detector keeps the classifier + kNN, the joint-OR threshold, incident grouping, volume ranking and one chart per incident (README §4, §5A–B, §6, §7). The README needs a matching rewrite (§0, §1, §2, §8–9).

---

## 3. Architecture

```
Web app (phone + laptop browsers on the same Wi-Fi; no internet needed)
   │  one chat: type, upload a file, or record from the mic
   ▼
Router (plain code, by file type, not an LLM)
   ├─ image/*        → vision model ─────────────────────────────┐
   ├─ video/*        → sample ~8 frames (OpenCV) → vision model  │
   ├─ audio/*        → Whisper transcript + sound ID → text model │→ answer + sources
   ├─ .pdf/.txt/.md  → chunk + retrieve → text model, "not found" check
   ├─ code request   → coder model → run in a sandbox → show output/tests
   └─ conn logs/CSV  → Strayline detector → incidents + charts → chat about any incident
```

### Models (decided by first tests; README §3 has the evidence)

| Job | Model |
|---|---|
| Images, video frames | **Qwen3-VL 8B** (`qwen3-vl:8b`) |
| Audio (speech + sounds), code, documents, general text, log briefings | **Gemma 4 E4B** (`gemma4:e4b-it-q4_K_M`) |
| Rejected | Qwen2.5-Coder 7B (failed code tests); Qwen3-VL for text-only prompts (empty answers) |

**Hardware for the slides:** MacBook Pro, Apple M4 Pro, 24 GB, Ollama 0.40.16, fully offline after setup.

### Status (Wed Nov 18, ~5 pm)
- [x] App: one chat page, laptop + phone, all five inputs plus logs, every answer shows its evidence and time
- [x] Code sandbox (no network, temp folder, 10 s) and one repair round
- [x] Practice-pack harness (`python -m desk.eval`), checked on a synthetic stand-in pack (10/11)
- [x] Strayline detector (lite) on Wednesday: 0.44% false alarms, DoS flood is incident #1
- [x] `setup.sh` for teammates' laptops; `tests/smoke_api.py` checks every input in ~2 min
- [x] Practice pack run (strict scorer): **71/100** proven automatically, **93/100** after a provisional review by the AI assistant (needs a teammate check); see results/test_results.md
- [ ] Speed up video (~65 s now): fewer or tiled frames; prefer specific sound labels ("Helicopter" over "Vehicle")
- [ ] Tune the log-briefing prompt (it over-flags normal incidents)
- [ ] Try the app from a phone; demo inputs (phishing screenshots, runbook, voicemails, screen recordings)
- [ ] Internal timed case, slides, rehearsal; move history to the IEEE org repo before Thu EOD

---|---|---|---|
| Image, video frames, charts | **Qwen3-VL 8B** (organizers' pick) | qwen2.5vl:7b (already installed) | Strong OCR and counting |
| Text answers, document QA | Qwen3-VL 8B (one model for both) | gemma3:12b (installed) | Fewer model swaps on 24 GB |
| Code | **qwen2.5-coder:7b** | qwen3-coder | Organizers' pick; fast |
| Speech to text | **Whisper** (local, e.g. mlx-whisper or faster-whisper, small/medium) | | Organizers' pick |
| Sound identification | **Gemma 4**, if Ollama accepts audio for it | A small audio classifier (e.g. YAMNet/CLAP) | **Test first**: the riskiest checklist item |

**Hardware for the slides:** MacBook (Apple M4 Pro, 24 GB), Ollama 0.40.16, fully offline.
**Ollama status:** qwen2.5vl:7b and gemma3:12b are installed. qwen3-vl, qwen2.5-coder and gemma4 still need pulling.
**Video needs** OpenCV (`pip install opencv-python`). ffmpeg isn't installed, and we don't need it.

---

## 4. How we work

Per the README: one laptop, everyone on every task, with P1/P2/P3 as a shared checklist. To use all three people anyway, the keyboard laptop builds while the other two prepare inputs: test files, the runbook document, slides, and the user interview.

| Track | What |
|---|---|
| **Build (at the keyboard)** | Everything in §5 |
| **Inputs (second laptop)** | Download the practice pack (Kaggle needs a login); make our own security test set: 3 phishing screenshots, 2 scam voicemails (recorded by us, no real people), a runbook PDF written by us, 2 screen recordings, one CIC-IDS2017 day |
| **Story (third laptop)** | User interview questions, slides, the 5-minute and 15-minute scripts, the hardware slide |

---

## 5. Schedule and gates

**The code deadline is Thursday EOD.** We freeze at **Thu 9 pm**, leaving 3 hours of buffer.

### Wednesday Nov 18 (now → midnight)

| Time | Build | Inputs / Story |
|---|---|---|
| 2:30–4:00 | Pull qwen3-vl, qwen2.5-coder, gemma4; install Whisper. **Spike the risky item:** can anything local identify a sound? | Download the practice pack; write the user one-liner |
| 4:00–7:00 | App skeleton: FastAPI + one chat page with upload and mic; router; **image** and **text** answers end to end | Write the runbook document (5–8 pages, ours); collect phishing screenshots (public examples or our own mocks) |
| 7:00–11:00 | **Audio** (Whisper + sound ID), **video** (frames → vision model), **code** (generate → run in sandbox → show result) | Record voicemails and screen recordings; prepare the internal rehearsal case |
| 11:00 | **Gate 1:** every one of the five inputs answers one practice item **in the app** | |

*Cut if behind at Gate 1:* "identify sounds" moves to the transcript only, and we say so (a named limit), with the code sandbox showing output only. Never cut a whole modality.

### Thursday Nov 19 (classroom 136/137, 10:00–4:30, then evening)

| Time | Build | Inputs / Story |
|---|---|---|
| 9:00–12:00 | **Test harness:** run the whole practice pack + our security set, score each item, write `results/test_results.md` (accuracy and seconds per item, per modality) | Slides: user, problem, architecture, model choices, limits |
| 12:00–3:00 | **Strayline detector (lite):** features → classifier + kNN → joint-OR thresholds → incidents → top list + charts, wired into the chat | **Internal timed case**: record task completion and errors |
| 3:00–4:30 | Usability pass: loading states, errors, "not in the document" message, mobile layout; check it works with Wi-Fi off | Add rehearsal observations and test results to the slides |
| 4:30–5:00 | Presentation prep (scheduled by organizers) | |
| 5:00–9:00 | Bug fixes only. README install/run steps from a clean clone. Move the history to the **IEEE org repo**. Rerun the harness for final numbers | Rehearse the 5-minute pitch twice |
| **9:00 pm** | **Gate 2, code freeze.** Push, tag `final`. Deadline is EOD | |

*Cut if behind at 12:00:* the Strayline detector shrinks to a pre-built incident list from one day's run, generated by our own code that night. If still behind at 3:00, it drops to a slide: "next step".

### Friday Nov 20 (no code changes)

| Time | |
|---|---|
| Morning | Two full rehearsals of the 5-minute pitch with Wi-Fi off; one of the 15-minute final. Pre-load the models. Phone on the same hotspot for the mobile demo. Backup laptop ready |
| 12:00 | Welcome and keynote |
| 1:00–4:00 | Round 1, then the final if we advance |
| 5:00 | Awards |

---

## 6. The 5-minute Round 1 pitch

Two judges give one score each, so the pitch has to show all five inputs fast.

| Time | Beat |
|---|---|
| 0:00–0:30 | **User and problem.** A campus IT analyst needs to triage a suspicious report while keeping the evidence on the laptop. |
| 0:30–2:05 | **Start video first.** Use the team's existing security clip. While it runs, explain the local models and why Strayline exposes each answer's supporting evidence. Show the sampled frames when the answer returns. |
| 2:05–4:20 | **Finish the same case with the other four inputs.** Show an image answer, the audio transcript, a supported runbook answer plus a detail the runbook doesn't contain, and a short Python function with its test result. Show the analyst's next action. |
| 4:20–5:00 | **Proof.** Show the organizer practice-pack counts by modality, distinguish automatically verified from provisional AI-reviewed results, name the hardware, and share any measured team rehearsal result. |

**15-minute final:** the same demo slower, then the full network-log replay, architecture and model choices, detailed test results, limits, impact evidence, and questions.

### Questions to prepare for

- Why these models? (Benchmarked on the practice pack; the size fits 24 GB; the organizers' recommendations.)
- What fails? (Name it from our test results: sound ID, counting in video, long documents.)
- How do you stop it making things up on documents? (Retrieval + an explicit "not found" check, shown live.)
- Is the generated code safe to run? (Sandboxed: timeout, no network, temp directory.)
- Why a security team? (Sensitive campus evidence stays local. Describe the team rehearsal if it was completed.)
- How fast on modest hardware? (Seconds per item from the harness.)
- Did you build this before? (The detector idea is from Kyle's earlier research; all code in this repo was written at the event, as the commit history shows.)

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| No local model identifies sounds | Spike it first (Wed 2:30). Fallback: a small audio classifier, or a named limit |
| Model swaps are slow on 24 GB | Keep 3 models max, pre-load before the demo, measure and show times |
| Code deadline is Thursday | Freeze 9 pm; no "Friday morning fixes" exist |
| Kaggle download needs a login | Make an account on the inputs laptop; our own security set is the fallback |
| No IEEE org repo yet | Already asked Vedanshi; keep pushing to ours; move with full history |
| Live demo fails | Every demo file preloaded locally; backup laptop; screen recording of a full run, used only if live fails and labelled as a recording |
| The detector eats the schedule | Hard cut at Thu 12:00 and 3:00 (see §5) |

---

## 8. Definition of done (Thu 9 pm)

- [ ] One web app, laptop and phone, offline: image, audio (incl. sound ID or a named limit), text with "not found", code that runs, video
- [ ] `results/test_results.md`: practice pack + our security set, per modality, accuracy and speed
- [ ] Strayline detector incidents in the chat (or explicitly cut at a gate)
- [ ] README: user, problem, install + run from a clean clone, models and why, hardware, limits, credits (datasets, models)
- [ ] Code in the IEEE org repo, tagged `final`, before EOD Thursday
- [ ] Slides (with hardware) and both scripts rehearsed
