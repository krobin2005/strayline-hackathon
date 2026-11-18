# Strayline: hackathon build spec

**Catching the attacks nobody has seen yet.**

This is the build spec for rebuilding Strayline from scratch at the **IEEE AI Hackathon 2026: Multimodal LLM Challenge** (Roux Institute, Portland ME, Nov 18–20, 2026). It covers the idea, the data, every feature formula, model, threshold rule, ranking rule, agent rule and evaluation protocol, how each event rule changes the original design, and the mistakes to avoid. It contains no code: everything is written during the event, in the team's assigned repo.

The schedule, roles and demo script are in the companion file, **`Strayline_hackathon_plan.md`**.

---

## 0. Hackathon rules and how this design complies

| Rule (Terms & Conditions) | What it means for Strayline |
|---|---|
| All code developed during the event, in the assigned GitHub repo; no "substantial pre-built implementations" | Nothing is copied from the original `strayline` repo: no code, trained models, cached features, site files or prompts. Only this spec (design, no code) and the public datasets come in. |
| No external cloud AI services during testing or demo rounds | The agents run on a **local** model through Ollama. No Anthropic, OpenAI or Google API calls anywhere in the runtime path. The app should start and run with Wi-Fi off. |
| AI "must not serve as underlying intelligence" during the demo | Ask the organizers at kickoff whether a local open-weights model in the pipeline is allowed. If not, ship the ML-only path (§8 fallback) and drop the agent layer. |
| No hard-coded answers or outputs | The demo runs the pipeline **live** on a log file, and every number on screen comes from that run. Any uploaded CSV or Zeek `conn.log` must work too. |
| Don't misrepresent originality or capabilities | The README and the pitch say plainly: "the design comes from my prior research (published repo); all code was written at this event." Figures from the prior research are labelled as such (§10), never presented as hackathon results. |
| Repos become public afterwards; respect dataset licences | No secrets, pitch or investor material, or pilot correspondence in the repo. Cite Engelen et al. 2021 and the CIC datasets. Data stays out of git; the README says how to download it. |
| README must have install, configuration and run instructions | One-command setup and one-command demo (see the plan file). |

**Email the organizers before you write any code** (ieeestudentbranchportland@gmail.com). Disclose the prior research and ask about local LLMs.

---

## 1. The idea in one paragraph

Most ML intrusion detectors only recognize attacks that look like their training data, so a new kind of attack walks straight through. Strayline combines two kinds of detector:
- an **attack classifier** trained on labelled lab traffic, which knows the attacks we already know;
- **anomaly detectors that learn the deployed network's own normal traffic**, with no labels needed.

Every connection is scored, alerts are grouped per source host into incidents, and a cheap ranking step picks the ~75 incidents worth an AI's attention. A **local multimodal model** then reads each incident two ways at once: as a structured card, and as a **rendered picture of the incident's traffic** (alerts over time, hosts and ports touched). It decides what to escalate and writes case reports, the way an analyst reads a dashboard.

Alongside the detector it publishes a **catchability map**: a measured table of which attack families it catches and which it misses. That tells a security team where to trust it.

### Why this fits the "Multimodal LLM" theme (and how we prove it)

The LLM isn't decoration. It handles the step the ML can't: deciding which of the remaining incidents is a coherent attack. The multimodal claim is **measured, not asserted**: we run triage on the same incidents as *text only* and as *text + chart*, and report escalation precision and recall for both (§9, protocol 6). If the chart doesn't help, we say so and present the text-only result.

### Targets for this build (measured at the event)

| Metric | Target |
|---|---|
| A held-out family (classifier trained without it) caught at a 2% false-alarm budget | DoS ≥ 90%; report every family in the catchability map |
| Measured false alarms on the replayed day's benign traffic | ≤ 2% |
| Funnel for one full CIC-IDS2017 day | ~400–550k connections → alerts → incidents → 75 to the AI → ≤ 20 escalations, attack incidents on top |
| Multimodal ablation | Text + chart precision vs text-only precision, reported honestly |
| AI cost at demo | $0, all local. Report wall-clock latency per incident instead |

The original research's numbers (87% cross-network and so on) are a reference only (§10).

---

## 2. Architecture

```
connection logs (CIC-IDS2017 CSV, or Zeek conn.log / NetFlow upload)
   │
   ├─ 19 per-connection features (flow-record fields only)
   ├─ 7 per-host features (one-minute aggregates per source and destination host)
   ▼
DETECTOR: three scores per connection
   A. lab classifier (MLP), inputs rescaled to the site
   B. kNN distance to the site's normal traffic (flow features only)
   C. autoencoder reconstruction error on the site's normal traffic (flow + host features)
   → alert if ANY score passes its threshold; thresholds jointly set so the union of
     alerts on normal traffic = budget (2%)
   ▼
INCIDENTS: alerts grouped per source host, split at 10-minute gaps, keep groups ≥ 10 alerts
   ▼
RANKING (no AI): top 50 by alert count  +  up to 25 "low-and-slow" incidents
   ▼
RENDER: one PNG per ranked incident (alert timeline, destination-host/port spread, score strip)
   ▼
LOCAL MULTIMODAL AGENTS (Ollama, offline):
   triage (card + chart → decision) → investigator (pre-fetched tool outputs + charts → case report)
   ▼
DEMO APP (local web server): live funnel, incident console, chart + rationale, catchability map
```

**ML-only fallback:** everything above RENDER runs without the LLM. If the local model is disallowed or fails on stage, the app still shows the ranked incident list with the "top unusual features" explanations.

---

## 3. Data

### Datasets

| Name | What | Use |
|---|---|---|
| **Improved CIC-IDS2017** (Engelen et al., 2021): `intrusion-detection.distrinet-research.be/CNS2022/` | ~2.1M labelled flows, 5 days (Mon 372k, Tue 322k, Wed 497k, Thu 362k, Fri 548k), CICFlowMeter features | **The core dataset.** Training, held-out-family tests, the live demo |
| Improved CSE-CIC-IDS2018 (same source, ~10 GB zip) | A different network | **Stretch only:** the cross-network test. Start the download on Day 1 in the background, and only use it if the core is done by Day 2 midday |

Use the *improved* versions. They fix labelling and feature bugs in the originals, which is also the answer to "isn't CIC-IDS2017 known to be broken?" Say so before a judge asks.

**Dropped from the original spec:** UWF-ZeekData24. Its benign and attack traffic are seven months apart, so it can't test detection, and there's no time for it.

### Labels → families

Map the raw labels to 7 families: **DoS** (Hulk, GoldenEye, Slowloris, Slowhttptest), **DDoS**, **PortScan** (incl. "Infiltration – Portscan"), **BruteForce** (FTP/SSH-Patator), **Botnet**, **WebAttack** (brute force, SQLi, XSS), **Infiltration**.

**Drop:** rows marked "Attempted", Heartbleed (11 flows), and unmapped labels.

### Days and what's on them (2017)

| Day | Contents | Role in this build |
|---|---|---|
| Monday | Benign only | Onboarding: the site's "normal" |
| Tuesday | Brute force | **Dev day** for ranking rules and prompts |
| Wednesday | DoS family | **Demo day**: replay live with DoS held out of the classifier |
| Thursday | Web attacks, infiltration | Test day: the low-and-slow queue, the multimodal ablation |
| Friday | Botnet, port scan, DDoS | Test day: the multimodal ablation, the catchability map |

### Splits

- **Chronological 60/20/20 within each (day × family) group:** train / validation / test.
- **Thresholds are always set on benign *validation* traffic only.** A detector must never see the attack it's tested on.
- Prompts and ranking rules are tuned on **Tuesday only**. Wednesday to Friday are touched only for final measurement.

### ⚠ Sampling trap

If you subsample, **compute per-host counts from the full data *before* sampling.** Otherwise attacker hosts look 20× busier than they are.

---

## 4. Features

Use only what a flow record (NetFlow/IPFIX biflow or Zeek `conn.log`) can provide. **Never use IPs, ports or timestamps as model inputs.**

### 4a. Per-connection features (19)

From the raw fields: `duration_us`, `proto`, `orig_pkts` (fp), `resp_pkts` (bp), `orig_bytes` (fb), `resp_bytes` (bb), plus TCP flags seen.

| Feature | Formula |
|---|---|
| Flow Duration | duration in µs |
| Protocol | IP protocol number (6 TCP, 17 UDP, 1 ICMP) |
| Total Fwd Packet / Total Bwd packets | fp / bp |
| Total Length of Fwd / Bwd Packet | fb / bb |
| Flow Bytes/s | (fb+bb) / duration_s, **0 if duration = 0** |
| Flow Packets/s | (fp+bp) / duration_s, 0 if duration = 0 |
| Fwd Packets/s, Bwd Packets/s | fp / duration_s, bp / duration_s (0 if duration = 0) |
| Fwd / Bwd Packet Length Mean | fb/fp, bb/bp (0 if no packets) |
| Average Packet Size | (fb+bb)/(fp+bp) |
| Down/Up Ratio | bp / fp, a **plain ratio, not rounded down** (0 if fp = 0) |
| FIN, SYN, RST, PSH, ACK flag | **presence bits 0/1**. From Zeek `history`: S=SYN, F=FIN, R=RST, A=ACK, D=data≈PSH, either case |

Leave out URG.

### 4b. Per-host features (7), computed per clock minute

| Feature | Definition |
|---|---|
| src_flows_1m | connections from this source host in this minute |
| src_dst_hosts_1m | distinct destination hosts it contacted |
| src_dst_ports_1m | distinct destination ports it contacted |
| src_short_frac_1m | share of its connections with ≤ 2 forward packets |
| dst_flows_1m | connections *to* this destination host in this minute |
| dst_src_hosts_1m | distinct sources contacting it |
| dst_short_frac_1m | share of short connections to it |

These make floods and scans obvious; in the original research, adding them took unseen DoS from 6% to 95%. **Excluded:** the per-host RST share, which is a capture artifact.

### 4c. Never use these (testbed artifacts)

TCP initial window bytes, minimum segment size, forward/backward header lengths, URG/CWR/ECE flags.

### 4d. Scaling

- Signed log1p: `z = sign(x) · log(1 + |x|)`.
- Standardize `(z − μ) / max(σ, 0.1)`, clip to ±10. Fit μ, σ on **benign training traffic only**.
- Refit μ/σ on the site's onboarding traffic, for the classifier's inputs too.

---

## 5. Models

Train on Apple MPS. Each model trains in seconds to a minute; budget a full retrain at under 10 minutes so you can rerun everything on Day 3 morning.

### A. Lab attack classifier (supervised)

- **MLP:** d → 128 → ReLU → Dropout 0.1 → 64 → ReLU → Dropout 0.1 → 1 logit.
- Adam, lr 1e-3, batch 2048, 8 epochs, BCE-with-logits, `pos_weight = n_benign / n_attack`.
- Up to 300k benign + up to 30k per attack family.
- **Held-out-family mode:** a `--hold-out <family>` flag trains without that family. This powers the demo and the catchability map.

### B. kNN distance (site anomaly arm 1)

20,000 random benign onboarding connections, **flow features only**. Score = mean Euclidean distance to the k = 5 nearest. Batched `cdist` on MPS.

### C. Autoencoder (site anomaly arm 2)

d → 64 → 32 → 16 → 32 → 64 → d (ReLU), MSE, Adam lr 1e-3, batch 2048, 20 epochs, up to 300k onboarding connections, **flow + host features**. Score = mean squared reconstruction error.

### Optional: Isolation Forest

200 trees, 4096 samples per tree. It's the contamination-robust backup.

### Onboarding (2017 setting)

The "site's normal" is Monday plus the benign *train* split of the other days. The next 20% of benign sets the thresholds.

---

## 6. Turning three scores into alerts

### Joint OR with one shared budget

```
normalize w so Σw = 1          (equal weights 1:1:1)
binary-search q in [0, B / max(w)] for ~40 iterations:
    threshold_i = quantile(benign_val_scores_i, 1 − wᵢ·q)
    union = fraction of benign_val rows where ANY score_i > threshold_i
    if union < B: raise q else lower q
```

B = 2%. Equivalent to taking each arm's benign percentile rank and alerting when the max rank passes one cut-off.

### Daily thresholds: stretch

Recomputing the thresholds nightly from yesterday's scores (each source host capped at 200 connections/hour) matters for real deployment. It's out of scope unless there's time. Mention it in the pitch as the deployment story.

---

## 7. Incidents and ranking

### Incidents

Sort alerts by time, group **per source host**, start a new incident after a **gap > 10 minutes**, keep incidents with **≥ 10 alerts**.

**Incident card** (what the agents see):
- id, pseudonymized src/dst, direction (int→int, ext→int, …)
- first seen, duration, alert count, alerts per minute
- protocols, distinct destination hosts and ports, top 5 ports
- share fired by the classifier vs by the anomaly arms
- median score percentiles
- top unusual features: |median z| vs the site's normal, typical value here vs the normal value

### Incident chart (the multimodal input)

One PNG per ranked incident, about 768×512, rendered identically for every incident, with **no labels and no real IPs**:
1. **Timeline:** alerts per minute over the incident's span, with the median for normal hosts drawn as a reference line.
2. **Spread:** destination hosts × destination ports touched (a dot matrix; scans fill it, floods are one bright cell).
3. **Score strip:** each arm's percentile per connection over time (classifier vs kNN vs autoencoder), which shows which arm "sees" it.

Use a fixed layout, fixed axes where possible, and a clear title of `incident id · src pseudonym · direction` only.

### Ranking: two queues, no AI

1. **Volume queue:** the 50 incidents with the most alerts.
2. **Low-and-slow queue (up to 25):** among the rest, incidents where the classifier fired on ≤ 20% of connections, **and** an anomaly arm fired on ≥ 80%, **and** the direction is external → internal, **and** the main destination port is in {21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 465, 587, 993, 995, 1433, 3306, 3389, 5432, 8080, 8443}. Rank by the anomaly arms' median percentile.

**Don't rank by "the classifier and the anomaly arms agree".** It fails on botnet (classifier-only) and web attacks (kNN-only).

---

## 8. Agents (local, multimodal)

### Runtime

- **Ollama** on the demo laptop (M4 Pro, 24 GB). Candidate models, picked by a Day 1 benchmark on Tuesday incidents:
  - **Qwen2.5-VL 7B:** the faster choice.
  - **Gemma 3 12B:** better quality if latency allows.
- Structured output through Ollama's JSON-schema `format` parameter. Temperature 0, fixed seed, so runs are repeatable.
- **One incident per triage call** (card + its chart), not batches of 20: small vision models degrade with many images per prompt. Keep the context block byte-identical across calls.
- **Latency budget:** measure seconds per incident on Day 1. If 75 incidents take longer than ~4 minutes, the live demo triages the top 20 on stage, and the full 75-incident run is shown from a log made earlier that day, with its timestamps.

### Ground rules

- **Pseudonymize every host** (`int-host-12`, `ext-host-40`). The dataset's IPs are well known.
- **No labels go to the agents.** Ground truth is joined afterwards, for scoring only.
- **Log every call:** model, input tokens, output tokens, latency, decision.

### Triage agent

**Input:** the incident card (text) + the incident chart (image) + a fixed context block.

**Structured output:**
- `decision` ∈ {escalate, monitor, dismiss}
- `priority` 1–5
- `suspected_behavior` ∈ {dos_flood, ddos, port_scan, brute_force, botnet_c2, web_attack, infiltration_lateral, benign_anomaly, novel_unclear}
- `visual_evidence`: one sentence on what the chart shows (for example "regular spikes every ~60 s", "fills the port axis")
- `rationale` (two sentences citing evidence)
- `confidence` 0–1

**If the model returns invalid JSON or skips a field**, retry once. If it fails again, escalate the incident with "no decision".

**Prompt rules that mattered in the original research:**
- **Explain each card field and each chart panel.** Percentiles are relative to normal traffic; the reference line is a normal host's median.
- **State the base rates.** Every incident is already unusual, so unusual alone is not evidence; expect 90%+ to be harmless.
- **Escalate on a *coherent pattern*:** volume or rate, spread across hosts or ports, regular repetition (beaconing), classifier agreement across tens of flows, or a strong anomaly-only signal *at scale*.
- **Keep escalations well under 15% of incidents.**
- **Rejected variant:** "prefer suspicious when unsure" produced 38/40 false escalations. Don't use it.

### Investigator agent (top 3–5 escalations)

Small local models are unreliable at multi-step tool calling, so **pre-fetch the tool outputs deterministically** and put them in one prompt, with no tool calls:

| Section | Contents |
|---|---|
| Incident | the card + the chart |
| Flows | that host's 30 most anomalous flows in the window, alerted or not |
| Host history | other incidents involving the host that day |
| Feature profile | top unusual features |
| Known families | the classifier's probability, plus the nearest family by centroid distance |
| Catchability | the measured catchability map, so the agent knows where the detector is blind |

**Report schema:** `summary`, `likely_attack_type` (including **`novel_unknown`** and **`benign_anomaly`**), `severity`, `confidence`, `evidence[]` (observed vs inferred kept separate), `blind_spot_warning`, `recommended_actions[]`, `open_questions[]`.

Stretch: real tool calling, if the chosen model supports it reliably in Ollama.

---

## 9. Evaluation protocols (do these honestly)

1. **Leave-one-family-out catchability map:** for each family, train the classifier without it and measure the share caught at 2%. Use 3 seeds (10 if time allows), and report Wilson intervals. Infiltration (36 flows) is indicative only.
2. **Live held-out replay:** Wednesday, DoS held out. Report the funnel and the measured false-alarm rate on the day's benign traffic.
3. **Full-day funnel:** connections → alerts → incidents → sent to AI → escalated → top priority, for each test day.
4. **Triage quality:** on Thu + Fri ranked incidents, report escalation precision, recall of attack incidents, and escalations per day.
5. **Latency:** seconds per incident (triage), per investigation, and per full pipeline.
6. **Multimodal ablation (the theme result):** the same incidents and the same model, (a) card only vs (b) card + chart. Report precision and recall for both, plus 2–3 concrete incidents where the chart changed the decision. **Fix this protocol before running it**, and run it on Thu/Fri, not on the dev day.
7. **Fix selection rules before you look.** If you change a rule after seeing test results, say so.
8. **Stretch: cross-network** (2017 → 2018) if the 2018 data is ready.

---

## 10. Prior research results (reference only; not hackathon results)

From the original Strayline research. Use these only as labelled context in the pitch ("previous work showed…"), never as this build's output.

| | Lab classifier only | Original v1 |
|---|---|---|
| 2017 → 2018, 2% budget, 1% contamination | 20% | 87% |
| 2018 → 2017 | 33% | 70% |

Per family (2017 → 2018): DDoS 100, port scan 99, brute force 100, DoS 99, botnet 96, web 74, infiltration 40. A full 2018 day: 6.5M connections → ~1,250 incidents → 75 to triage → 19 escalations, top 3 all the real intrusion.

---

## 11. Mistakes to avoid

| Trap | Fix |
|---|---|
| Timestamp units (`/1e9` on µs squeezed a day into 1.7 h) | Convert via `(ts − epoch).total_seconds()`; assert a day spans ~24 h |
| Feature formula drift | Compute features one way for training and serving |
| Uneven sampling inflates host counts | Aggregate per host on the full data, then sample |
| Capture artifacts (RST share, ECE/CWR, window size) | Drop them |
| kNN learns attacks in onboarding as normal | Keep the classifier in the OR |
| Agreement ranking | Volume + low-and-slow queues |
| Reused output folders | Wipe the run folder at the start of every run |
| Over-eager prompt | Base rates and pattern rules |
| **Hackathon:** copying from the old repo | Never open old source files while coding; build from this spec only |
| **Hackathon:** a cloud API left in a code path | No cloud SDKs in requirements; test the demo with Wi-Fi off |
| **Hackathon:** a static demo | Every on-screen number comes from a run triggered in the app |
| **Hackathon:** quoting old numbers as new | Prior results only in a labelled "prior work" slide |
| **Hackathon:** slow local LLM on stage | Benchmark on Day 1; live triage on the top 20 if needed |
| **Hackathon:** scope creep | Finish the core in the plan file before any stretch goal |

---

## 12. Stack

- Python 3.11+, pandas/pyarrow, PyTorch (MPS), scikit-learn
- matplotlib for incident charts (headless, Agg backend)
- Ollama + Qwen2.5-VL 7B or Gemma 3 12B (local, offline)
- Demo app: FastAPI (or Flask) serving a static HTML/JS page. Endpoints: start a run, stream progress, list incidents, get an incident with its chart and agent output, get the catchability map. Upload a CSV or `conn.log`.
- **No cloud AI SDKs** in `requirements.txt`.

---

*Strayline, by Kyle Robin (Bates College '29). The design, numbers and lessons come from the original research (github.com/krobin2005/strayline); the hackathon code is written fresh at the event.*
