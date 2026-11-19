# Strayline Desk

**An offline AI assistant for a small college's IT security team.**

Strayline Desk runs on one laptop with open-weight models and no internet connection. It works with everything a campus security analyst handles in a day: phishing screenshots, scam voicemails, policy documents, scripts, screen recordings and network logs. None of that data ever leaves the building.

Built for the **IEEE AI Hackathon 2026: Multimodal LLM Challenge** (Roux Institute, Portland ME, Nov 18–20, 2026). The schedule, gates and demo scripts are in **[PLAN.md](PLAN.md)**.

Start with the [five-input rehearsal](demo/README.md), the [recorded practice results](results/test_results.md), and the install instructions in section 8.

## How we work

We design, build, test, and rehearse together on one laptop at a time. Everyone shares responsibility for each task, whoever is at the keyboard. We use the work listed in [PLAN.md](PLAN.md) as a shared checklist. The schedule and demo script are there too.

---

## 1. The user and the problem

**User:** the IT security staff of a small college: a handful of people defending thousands of students and staff.

**Problem:** their evidence is sensitive. Logs show who visited what, voicemails and screenshots contain names and accounts, and incident notes describe real people. Pasting any of it into a cloud AI tool sends student and staff data to a third party, so they need a way to analyze it locally. They also handle every kind of input, not just text.

**What Strayline Desk does:** one chat, five kinds of input plus network logs, all answered by local open-weight models. It works offline, costs nothing per request, and can't change its terms or disappear.

| Input | General ability (the challenge checklist) | Security job (our user) |
|---|---|---|
| **Image** | Describe a photo and answer questions about it | "Is this email screenshot phishing? What gives it away?" |
| **Audio** | Transcribe speech, answer questions, identify sounds | A voicemail reported as a scam: transcript, what the caller wants, background sounds |
| **Text** | Answer questions about a document; say so when the answer isn't there | "Who do we notify about a compromised account?" from the incident-response runbook |
| **Code** | Write working code from a prompt | "Write a function that finds hosts contacting more than 100 ports in a minute", then run it on a log |
| **Video** | Describe a short clip and answer questions about it | A screen recording a user sent of a fake "tech support" pop-up, step by step |
| **Logs** *(our addition)* | | **Strayline detector:** a day of connection logs → ranked incidents → ask about any incident in the chat |

---

## 2. Architecture

```
Browser (laptop or phone on the same local network; no internet needed)
   │   one chat: type, upload a file, or record from the mic
   ▼
FastAPI server on the laptop
   │
Router (plain code, by file type and request, never an LLM)
   ├─ image            → vision-language model ──────────────────────────────┐
   ├─ video            → sample frames (OpenCV) → vision-language model       │
   ├─ audio            → Gemma transcript + AudioSet sound labels → LLM      │
   ├─ document         → chunk + retrieve → LLM, with a "not found" check     ├→ answer
   ├─ code request     → coder model → run in a sandbox → show code + output  │   + evidence
   └─ connection logs  → Strayline detector → ranked incident cards → LLM        ┘
```

Design rules:
- **Fully local.** Ollama serves every model on `localhost`. No cloud AI SDKs are installed, and the app is tested with Wi-Fi off.
- **Plain-code routing.** File type decides the path, which is fast, predictable and easy to explain.
- **Show the evidence.** Every answer shows what it was based on: the transcript, the frames, the document passage, the code's output, or the detector counts.
- **Local models** are preloaded on the 24 GB demo laptop. Model choice is per job (§3).

---

## 3. Models and why

Ollama serves the language and vision models on the laptop. The sound classifier runs in a separate local Python pipeline.

| Job | Model | Why |
|---|---|---|
| Image questions | Qwen3-VL 8B | Reads screenshots and answers visual questions with one image per request. |
| Documents, code, briefings and speech | Gemma 4 E4B | Handles text and WAV input locally. The code path runs generated functions against tests. |
| Environmental sound identification | MIT Audio Spectrogram Transformer, fine-tuned on AudioSet | Provides ranked sound labels and scores independently of the transcript. |

**Rejected on first test:**
- **Qwen2.5-Coder 7B** (organizers' code pick): failed the port-scan task 2/2. Its fix after seeing the failing test was worse.
- **Qwen3-VL 8B for text-only prompts:** returned an empty answer after ~100 s on the code task, apparently spending the whole reply on hidden reasoning even with `think: false`. Fine on image prompts.

**Hardware:** MacBook Pro, Apple M4 Pro, 24 GB RAM, Ollama 0.40.16.

---

## 4. How each input works

### Image
- The image + question go to the vision model. With no question, the default is: describe it, then list anything that looks suspicious if it's a screenshot.
- Phishing check prompt: sender, link text vs real URL, urgency, requests for credentials or money, branding mismatches. The answer is a verdict with reasons.

### Audio
1. The AudioSet classifier scans ten-second windows across the recording. The evidence panel shows its strongest supported sound labels.
2. When the classifier detects speech, Gemma transcribes the recording in 25-second chunks. A missed speech detection can leave the transcript empty.
3. Gemma answers using the transcript and the sound evidence. For short speech clips it also receives the audio.
- The page converts mic recordings, MP3 and M4A to 16 kHz WAV in the browser; the server falls back to macOS `afconvert`.

### Text (documents)
1. Accept PDF, TXT and Markdown. Split into 180-word overlapping chunks with page numbers.
2. Retrieve the most relevant chunks for the question with BM25.
3. Answer **only from those chunks**, quoting the page.
4. **"Not in the document":** the prompt requires an exact `NOT_FOUND` reply when the chunks don't contain the answer, and the app shows "This isn't in the document." We test this explicitly: the practice pack has questions with no answer.

### Code
1. The coder model writes a Python function from the prompt.
2. The app **runs it in a sandbox**: a separate process, 10-second timeout, temporary directory, no network, and only the uploaded file is readable.
3. It shows the code, its output, and the result of any tests. If it fails, the error goes back to the model once for a fix.

### Video
1. Sample ~8 evenly spaced frames with OpenCV (more for longer clips, up to a cap), each labelled with its timestamp.
2. Send them to the vision model in order, asking for a step-by-step description.
3. Answer follow-up questions from the frames + that description. Counting and motion questions use more frames.

### Logs: the Strayline detector (lite)

Turns a day of connection logs into a short list of incidents, without labels. Input: CIC-IDS2017 CSV, or a Zeek `conn.log` if time allows.

**Features (19 per connection + 7 per host-minute).** Only fields a flow record has; never IPs, ports or timestamps as model inputs.

| Feature | Formula |
|---|---|
| Flow Duration | duration in µs |
| Protocol | IP protocol number |
| Fwd / Bwd packets, Fwd / Bwd bytes | fp, bp, fb, bb |
| Flow Bytes/s, Flow Packets/s | (fb+bb)/s, (fp+bp)/s; **0 if duration = 0** |
| Fwd / Bwd Packets/s | fp/s, bp/s (0 if duration = 0) |
| Fwd / Bwd Packet Length Mean | fb/fp, bb/bp (0 if no packets) |
| Average Packet Size | (fb+bb)/(fp+bp) |
| Down/Up Ratio | bp/fp, plain ratio (0 if fp = 0) |
| FIN, SYN, RST, PSH, ACK | presence bits 0/1 |

Per host, per clock minute: `src_flows_1m`, `src_dst_hosts_1m`, `src_dst_ports_1m`, `src_short_frac_1m` (share with ≤ 2 forward packets), `dst_flows_1m`, `dst_src_hosts_1m`, `dst_short_frac_1m`. **Compute these on the full data before any sampling.**

**Never use:** TCP window sizes, segment size, header lengths, URG/CWR/ECE, per-host RST share (capture artifacts).

**Scaling:** signed log1p, then `(z − μ) / max(σ, 0.1)`, clipped to ±10, with μ and σ fit on benign training traffic.

**Two detectors:**
- **Classifier:** MLP d → 128 → 64 → 1 (ReLU, dropout 0.1), Adam 1e-3, batch 2048, 8 epochs, `pos_weight = n_benign / n_attack`, trained on labelled CIC-IDS2017 days other than the demo day.
- **kNN anomaly score:** mean distance to the 5 nearest of 20,000 benign "normal" connections (flow features only). Catches what the classifier never saw.

**Alerts:** alert if either score passes its threshold. Thresholds are set jointly on benign validation traffic so that 2% of normal connections alert in total (binary search over each arm's quantile).

**Incidents:** group alerts per source host, split at gaps over 10 minutes, keep groups of ≥ 10 alerts. Rank by alert count; show the top 20.

**In the chat:** each incident has a card with a pseudonymized source, duration, rate, hosts and ports touched, and detector signals. The language model uses those cards for its briefing.

**Mistakes to avoid** (from earlier research): timestamps in µs divided as if ns (assert a day spans ~24 h); different feature code for training vs serving; per-host counts computed after sampling.

---

## 5. App

- **FastAPI** server + one HTML/JS page, all assets local (no CDNs), so it works with no internet.
- **One chat** with: text box, file upload (any of the five types or a log), mic button, and an incident table in log replies.
- **Mobile:** the server listens on the local network; a phone on the same hotspot opens the same page (judging bonus for web + mobile). The layout works at phone width.
- **Usability:** a progress message while a model runs ("transcribing… 6 s"), clear errors, and the evidence for every answer.

---

## 6. Testing ("your own test results")

- **Practice pack** (not scored by the organizers): 25 image, 20 audio, 20 text, 20 code, 15 video items in the same format as the Day 3 items, which judges pick at random and answer live with Wi-Fi off. Kaggle: `bhavyasreepylaa/ieee-ai-hackathon-2026-practice-pack` (needs a Kaggle login). **Its rules: never commit the pack or its answers; no fine-tuning; never look up answers in the source datasets' labels.**
- **Our security set:** a fictional account-recovery case with a locally synthesized voicemail, a notice, a runbook, and a short clip; plus one CIC-IDS2017 day.
- **Harness:** `python -m desk.eval` runs every item through the same handlers as the app and writes `results/test_results.md` (aggregates only). Scoring: code by the pack's own unit tests in the sandbox; unanswerable text questions must say "not in the document"; counts by the number; transcripts by word error rate (≤ 25%); short answers by normalized match; long free-form answers marked "needs review" for a person instead of guessed. Checked on a synthetic stand-in pack: 10/11 (the miss was a pure test tone, see Limits).
- **Detector:** share of attack connections alerted and the false-alarm rate on the demo day's benign traffic.

**Practice pack, 100 items (Nov 18, audio and code rerun Nov 19), [full table](results/test_results.md): 76/100 proven by the strict automatic scorer; 95/100 after a provisional review of the free-form answers by our AI coding assistant. A teammate still needs to confirm that review.**

| Input | Proven automatically | After provisional review | Median time |
|---|---|---|---|
| Image | 21/25 | 23/25 | 8 s |
| Audio | 15/20 | 19/20 | 7 s |
| Text | 18/20 | 20/20 | 5 s |
| Video | 2/15 | 13/15 | 62 s |
| Code | 20/20 (pack's unit tests) | 20/20 | 28 s |

What moved the numbers:
- **Sounds:** an AudioSet classifier went from about 1/10 with Gemma 4 alone to about 8/10.
- **Sound answers:** naming the source and action ("a rooster crowing", not "Cock-a-doodle-doo"), with each label's AudioSet parent category, moved audio from 11/20 to 15/20 proven automatically. Measured on the same clips, so it needs a check on new sounds.
- **Code:** a second fix round took code from 19/20 to 20/20, at a median 28 s instead of 19 s.
- **Text:** a rule that says "if the details don't match, it's not in the document".
- **Video:** separate frames instead of one contact sheet (13/15 vs 6/15).

---

## 7. Limits (named, not hidden)

*(Update from the practice-pack results.)* So far:
- Sounds: the classifier sometimes gives a generic label ("Vehicle" for a helicopter, "Crackle" for a fire) or mishears (ocean waves → boat). Pure synthetic tones can't be identified.
- Video is the slowest input (~65 s): 10 frames cost ~10,500 tokens in Qwen3-VL, and shrinking frames doesn't help (Ollama resizes them itself). Next step: fewer frames, or several frames tiled into one image. Counting objects that appear one at a time and counting bounces are the weak questions.
- A cold video question takes ~50 s while Qwen3-VL loads with its 20k-token context. The app pre-loads both models at start (Gemma first, then Qwen3-VL; the other order evicted Qwen3-VL), after which a video question takes ~5 s. Start the app a minute before the demo.
- On a phone, the mic button is hidden: browsers only allow the mic on secure pages, and the laptop's local address is plain http. Phones can upload a voice memo instead.
- Counting and fast motion in video depend on frame sampling.
- Long documents are limited by retrieval quality.
- Generated code runs only in the sandbox; it's a helper, not an autonomous agent.
- The detector is trained and tested on lab traffic (CIC-IDS2017), not a real campus network.

---

## 8. Setup and run

### On a new laptop (macOS or Linux), once
1. Install **Python 3.11+** (python.org) and **Ollama** (https://ollama.com/download; on a Mac, unzip it, drag `Ollama.app` into Applications and open it once).
2. Clone this repo and run:
   ```bash
   sh setup.sh
   ```
   It creates `.venv`, installs the packages, starts Ollama, downloads the two models (`qwen3-vl:8b` and `gemma4:e4b-it-q4_K_M`, ~13 GB the first time) and checks a model answers. Safe to run again.

Hardware note: built and tested on an Apple M4 Pro with 24 GB RAM. 16 GB machines should work but slower; under 16 GB, expect long waits.

### Every time
With Ollama open:
```bash
.venv/bin/python -m desk
```
It prints `http://localhost:8000` for this laptop and a `http://<laptop-ip>:8000` address for a phone on the same Wi-Fi or hotspot, and loads both models in the background so the first question is fast. The status dot turns green when the models are reachable. No internet is needed after setup.

Works now: **image, audio (speech + sounds, mic or file), document (with "This isn't in the document."), video, code (written, run in a sandbox, tested), and logs (upload a day of CIC-IDS2017 CSV → ranked incidents + briefing)**, plus plain questions.

### Checks
- Everything at once, app running: `.venv/bin/python tests/smoke_api.py`
- Practice pack: download it from Kaggle (needs a Kaggle login), unzip into `data/practice/` so that `data/practice/practice_pack/items.json` exists, then:
  ```bash
  .venv/bin/python -m desk.eval
  ```
  Add `--only audio --limit 5` for a quick run. Writes `results/test_results.md`; per-item answers stay in git-ignored `data/eval/` because the pack must not be published.
- Harness self-check without the real pack: `.venv/bin/python tests/make_mini_pack.py` then `.venv/bin/python -m desk.eval --pack data/mini_pack --summary data/mini_pack/results.md`

### Data and training for the detector (only for logs)
CIC-IDS2017 improved, 328 MB zip, git-ignored. After unzipping, train once (~15 s; `setup.sh` does this automatically when the data is there), then try it on Wednesday, a day the classifier never saw:
```bash
.venv/bin/python -m desk.detector train
```
```bash
.venv/bin/python -m desk.detector score data/raw/wednesday.csv
```
In the app, attach `data/raw/wednesday.csv` (291 MB) and ask "Which incidents should I look at first?".

First result (Wednesday, never seen in training): 496,641 connections → 170,927 alerts → 33 incidents in 26 s; 0.44% of normal connections alerted (budget 2%); 98.3% of labeled attack connections alerted; the DoS flood is incident #1. These are results from public lab traffic. The briefing uses pseudonymized incident cards.

Download:
```bash
mkdir -p data/raw && curl -L -o data/raw/CICIDS2017_improved.zip https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/CICIDS2017_improved.zip
```
```bash
cd data/raw && unzip CICIDS2017_improved.zip
```

---

## 9. Rules we follow

| Rule | How |
|---|---|
| Open-weight models only, running locally | Ollama + a cached AudioSet classifier on the laptop; no cloud AI anywhere; tested offline |
| AI coding tools for writing code, not as the system's brain | We used AI assistants to help write code; the app's answers come only from the local models |
| All code written during the event | This repo's history starts Nov 18, 2026. The detector design comes from Kyle's earlier Strayline research; no code, models or files were copied from it |
| No hard-coded answers | Every answer in the demo is produced live; the harness runs the same code path |
| Public repo in the IEEE GitHub organization, README with install and run steps | §8; we move this history to the org repo when it's assigned |
| Licences | Datasets and models are credited below; no data or model weights in the repo |

---

## 10. Credits

- CIC-IDS2017, improved version: Engelen, Rimmer & Joosen, "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study" (2021), and the Canadian Institute for Cybersecurity.
- Models: Qwen3-VL and Qwen2.5-Coder (Alibaba Qwen), Gemma 4 (Google), Whisper (OpenAI), served by Ollama.
- IEEE AI Hackathon 2026 practice pack (IEEE Student Branch, Roux Institute).
- AudioSet ontology (Google, CC BY-SA 4.0): the parent category of each sound label, in `desk/handlers/audioset_parents.json`.

*Team: Kyle Robin, Liam Baron, Zac Bower (Bates College).*
