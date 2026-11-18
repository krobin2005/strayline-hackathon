# Strayline: 3-day hackathon plan

IEEE AI Hackathon 2026, "Multimodal LLM Challenge", Nov 18–20, 2026 (all times ET). Prize: $900.
The technical design is in **`README.md`**, referred to below as "the spec". This file is the *when, who and how we win*.

---

## 1. What we're submitting

**One sentence:** a local, offline system that catches network attacks it was never trained on, and uses a multimodal model that *looks at* each incident's traffic to decide what a human should read. We measure how much the visuals help, and publish exactly where the system is blind.

**The demo moment:** we train the attack classifier *without* DoS, then replay Wednesday's traffic live. The DoS flood still gets caught by the anomaly detectors, lands at the top of the incident list, and the local vision model explains the flood by pointing at its chart. Wi-Fi off the whole time.

---

## 2. Winning against the criteria

The official criteria are announced at kickoff. The T&C say projects are judged on "actual functionality, performance, and output". Until we see the real list, we plan against the usual categories, and **re-weight this table at 3 pm on Day 1**.

| Likely criterion | How we score | Evidence on stage |
|---|---|---|
| **Works live (functionality)** | Pipeline runs end to end from a raw log in the app, plus an upload of any CSV / `conn.log` | Click "Run", watch the funnel fill |
| **Performance / output quality** | Held-out-family detection, false alarms ≤ 2%, escalation precision | Catchability map, measured FPR, precision/recall table |
| **Theme: multimodal LLM** | The vision model reads a chart + card per incident; the **ablation** shows whether the image helps | Text-only vs text+chart table, 2–3 incidents where the chart changed the call |
| **Technical depth / innovation** | Supervised + site-learned anomaly arms, one shared false-alarm budget, two-queue ranking | 30-second architecture slide |
| **Real-world impact** | Funnel from ~500k connections to ≤ 20 to read; runs offline, so data never leaves the site; $0 per day | Funnel numbers, "Wi-Fi is off" |
| **Honesty / rigor** (ML judges notice) | Chronological splits, thresholds only on benign, dev/test days separate, blind spots shown | Catchability map with weak families in red, "prior work" clearly labelled |
| **Presentation** | A tight 4–5 minute story, one live run, no slide walls | Rehearsed twice |

**Rule:** if kickoff reveals a criterion we don't cover, it goes into the Day 2 plan ahead of every stretch goal.

---

## 3. Team and ownership

| Person | Owns (spec sections) | Also |
|---|---|---|
| **P1, Detector** | Data loading, families, splits, the 26 features, scaling, three models, joint-OR thresholds, held-out-family training, catchability map (§3–6, §9.1) | Final measurement runs |
| **P2, Incidents + agents** | Incident grouping, cards, two-queue ranking, incident charts, Ollama runtime, triage + investigator prompts, ablation (§7–8, §9.4–9.6) | Model benchmark on Day 1 |
| **P3, App + pitch** | Local web app (funnel, incident console, chart + rationale view, catchability heatmap, upload), README, slides, demo script | Organizer contact, rule questions, timekeeping |

If there are only two of us, P3's app work moves to P2 after Gate 2, and P1 takes the slides.

### Contracts between people (agree on these in the first hour)

Everyone works against these files, so nobody waits on anyone. Each run writes to a fresh `runs/<run_id>/` folder (wiped at start).

| File | Written by | Read by | Contents |
|---|---|---|---|
| `flows.parquet` | P1 | P1, P2 | One row per connection: pseudonymized src/dst, ts, raw fields, 26 features, label (eval only) |
| `scores.parquet` | P1 | P2, P3 | Three arm scores, percentiles, alert flag, which arm fired |
| `incidents.json` | P2 | P3 | Cards (spec §7), queue (volume / low-and-slow), rank |
| `charts/<incident_id>.png` | P2 | P2 agents, P3 | Incident chart |
| `triage.jsonl` | P2 | P3 | One line per incident: decision, priority, behaviour, visual_evidence, rationale, confidence, latency |
| `investigations/<id>.json` | P2 | P3 | Case reports |
| `funnel.json` | P2 | P3 | Counts at each stage + measured FPR |
| `catchability.json` | P1 | P2 (investigator), P3 | Family × caught share, intervals, seeds |

P3 may build the UI against a **hand-made sample** of these files on Day 1. **Delete all sample fixtures before Gate 4.** Every number in the final demo must come from a real run (no hard-coded outputs).

---

## 4. Before writing code (status as of Wed Nov 18, ~2 pm)

We missed the kickoff session (1–4 pm on Teams) because of class, so we're catching up by email.

**Done**
- [x] Prior-work disclosure and local-LLM question sent to Shubham Gajjar (organizer) on Nov 16. No reply yet.
- [x] Local-LLM question sent to ieeestudentbranchportland@gmail.com on Nov 18.
- [x] Team repo created: `krobin2005/strayline-hackathon` (private), with README (spec) and PLAN. Liam (LiamBaron5) and Zac (Zac5858) invited with write access.
- [x] CIC-IDS2017 CSVs on Kyle's laptop (2.1M rows across 5 days).

**To do now**
- [ ] **Find out what we missed at kickoff.** Check the Teams meeting chat, or ask Vedanshi Shah (shah.vedans@northeastern.edu) by replying to the "Hackathon Day 1" thread. We need:
  1. The **problem statement** and **judging criteria**. Re-weight §2 the moment we have them.
  2. Whether there's an **official team repo**. If so, push our history to it (`git remote add official <url> && git push official main`).
  3. The **submission deadline** on Day 3 and the **presentation length**.
  4. What the **testing rounds** involve: will judges bring their own inputs?
- [ ] Liam and Zac: accept the GitHub invites.
- [ ] **Install Ollama** and pull both candidate models (`qwen2.5vl:7b`, `gemma3:12b`). It's a big download, so start it first.
- [ ] Copy the CIC-IDS2017 CSVs to every laptop that will run code (they stay out of git).
- [ ] Optional: start the CSE-CIC-IDS2018 download (10 GB) in the background for the stretch goal.
- [ ] Keep the old `strayline` repo closed while coding. Only the spec is open.

**If the organizers say no to local LLMs:** the Gate 2 ML-only demo becomes the submission (see §7).

---

## 5. Schedule and gates

Each gate has a **cut list**: if we're behind at the gate, we cut those items and move on. We don't let one part sink the demo.

### Day 1: Wed Nov 18 (kickoff 1 pm, then evening)

| Time | P1 | P2 | P3 |
|---|---|---|---|
| 1:00–2:45 | Kickoff, Q&A, rules | Kickoff, Q&A | Kickoff; send organizer email |
| 2:45–3:30 | **Whole team:** re-weight §2 against the real criteria; agree on the contracts in §3; repo skeleton, README stub | | |
| 3:30–7:00 | Loader, families, drops, chronological splits, 19 flow features, 7 host features (correct timestamp handling) | Ollama benchmark: both models on 5 hand-drawn test charts, measuring seconds/incident and JSON validity. **Pick a model by 7 pm** | App skeleton: local server + page with funnel and incident list, against sample files |
| 7:00–11:00 | Scaler, MLP (with `--hold-out`), kNN, autoencoder; scores on Tuesday | Incident grouping + cards on P1's Tuesday scores (or sample scores until they land) | Incident detail view (card + chart + rationale), catchability heatmap component |

**Gate 1, Wed 11 pm:** three arms score Tuesday; incidents exist for Tuesday; a model is picked with a measured latency.
*Cut if behind:* the autoencoder (kNN + classifier only), the investigator agent.

### Day 2: Thu Nov 19 (workspace 9 am–5 pm, then evening)

| Time | P1 | P2 | P3 |
|---|---|---|---|
| 9:00–11:00 | Joint-OR thresholds; Wednesday replay with DoS held out; measured FPR | Two-queue ranking; incident chart renderer (3 panels) | Wire the app to real `runs/` output; "Run" button + progress stream |
| 11:00–1:00 | Catchability map: leave-one-family-out, 3 seeds | Triage prompt v1 on **Tuesday only** (dev day); JSON schema, retries, call log | Upload path: CSV / `conn.log` → same pipeline |

**Gate 2, Thu 1 pm:** a live Wednesday run in the app shows the funnel and a ranked list, with no LLM. **This is the minimum demo; it must never break from here on.**
*Cut if behind:* upload, low-and-slow queue, daily thresholds, 2018.

| Time | P1 | P2 | P3 |
|---|---|---|---|
| 1:00–5:00 | Hardening: one command runs everything; full-pipeline timing; Wi-Fi-off test | Triage v2 (still Tuesday); investigator with pre-fetched context; **freeze prompts by 5 pm** | Slides draft: problem, idea, architecture, results placeholders |
| 5:00–10:00 | Final catchability run (more seeds if time) → `catchability.json` | **Ablation** on Thu + Fri incidents: text-only vs text+chart (protocol fixed in advance, spec §9.6) | Demo script v1; README install/run instructions; first full rehearsal at 9 pm |

**Gate 3, Thu 10 pm:** live triage in the app with the local model; investigator reports for the top 3; ablation numbers measured; catchability map real.
*Cut if behind:* the investigator (triage only), extra seeds, polish.

### Day 3: Fri Nov 20 (presentations from ~1 pm)

| Time | Everyone |
|---|---|
| 8:00–10:00 | Fresh run of everything from a clean checkout (proves the README works). Fill the slides with these numbers only. Delete sample fixtures. |
| 10:00–11:00 | **Gate 4, code freeze.** Push, tag `final`. Two full rehearsals with Wi-Fi off, timed. |
| 11:00–12:00 | Buffer. Pre-warm the model (first call loads weights). Charge laptops. Backup: a screen recording of a full live run, made this morning, in case the live run fails. |
| 12:00 → | Event; presentations from ~1 pm |

*Adjust Gate 4 to the real submission deadline once the organizers confirm it.*

### Stretch goals (only after Gate 3, in this order)

1. Isolation Forest arm (contamination robustness).
2. Daily thresholds with the per-host cap.
3. Cross-network 2017 → 2018 (needs the 2018 download and per-host aggregation on the raw files).
4. Real tool calling for the investigator.

---

## 6. Demo script (target 4–5 minutes; adjust to the real slot)

| Time | Beat | What's on screen |
|---|---|---|
| 0:00 | **Problem.** "Detectors learn yesterday's attacks. The one that hurts is the one nobody has seen." | One slide |
| 0:30 | **Idea.** One model learns known attacks; the others learn only what *this* network's normal looks like. | Architecture slide |
| 1:00 | **Live.** "This classifier has never seen a DoS attack. Wi-Fi is off. Run Wednesday." | App: click Run, funnel fills: ~500k → alerts → incidents → 75 → escalations |
| 2:00 | **The AI looks.** Open the top incident: its chart, and the model's `visual_evidence` + rationale. | Incident view |
| 2:45 | **Does the picture matter?** Text-only vs text+chart precision/recall, and one incident where the chart flipped the call. | Ablation table |
| 3:30 | **Where not to trust it.** Catchability map, weak families shown honestly. | Heatmap |
| 4:00 | **Why it's real.** Offline, $0, data never leaves the site; built on prior research (labelled), all code written this week. | Closing slide |

### Questions to prepare for

- "Isn't CIC-IDS2017 flawed?" → We use the improved version (Engelen 2021), drop capture-artifact features, and use only flow-record fields.
- "Isn't this overfit?" → Chronological splits, thresholds set on benign only, prompts tuned on Tuesday and tested on Thu/Fri, held-out family.
- "Why not just a bigger classifier?" → It can't catch what it never saw; the catchability map shows exactly that.
- "Why an LLM at all?" → It only reads 75 incidents, does the analyst's coherence judgement, and the ablation measures what the image adds.
- "Did you build this before?" → The research and design, yes, disclosed to the organizers; the code, no: it's all in this repo's commit history from this week.
- "How fast is it?" → Quote measured numbers: pipeline minutes per day, seconds per incident.

---

## 7. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Local LLM disallowed | Low–medium | Ask at Q&A. ML-only fallback is Gate 2's demo; pitch shifts to "detection + ranking" |
| Local model too slow on stage | Medium | Day 1 benchmark; live triage on top 20; full run shown from a timestamped log of a real run |
| Vision model doesn't help (ablation flat or negative) | Medium | Report it honestly; it's still a measured result. Keep the chart as the analyst's view |
| Criteria favour something we don't do | Medium | Re-weight at 3 pm Day 1 |
| Timestamp / sampling bugs inflate host features | Medium | Spec §11 checks: assert a day spans ~24 h; aggregate before sampling |
| Demo laptop fails | Low | Second laptop with the repo + models installed; screen recording backup |
| Prior-work challenge | Low (if disclosed) | Email on Day 1; commit history; "prior work" slide |

---

## 8. Definition of done (Gate 4)

- [ ] `git clone` → README steps → one command runs the full pipeline on a 2017 day, offline.
- [ ] The app runs a replay live and shows the funnel, ranked incidents, charts, triage output and the catchability map, all from that run's files.
- [ ] Upload of a CSV or `conn.log` works (or was explicitly cut at Gate 2).
- [ ] Measured: held-out-family detection, FPR on the day, escalation precision/recall, ablation, latency.
- [ ] No cloud AI calls anywhere; tested with Wi-Fi off.
- [ ] No sample fixtures, secrets, pitch/investor or pilot material in the repo.
- [ ] README credits the prior research and the datasets.
- [ ] Rehearsed twice, under time.
