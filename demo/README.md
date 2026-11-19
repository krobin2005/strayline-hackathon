# Five inputs, one account-recovery ticket

Use the files in this directory on the presentation laptop. North Hall College and ticket NH-184 are fictional. The screenshot and video were rendered for this case. The caller is a locally synthesized eSpeak NG voice. No campus records or student voices are included.

| Input | Ask the app | Check on screen |
|---|---|---|
| recovery-notice.png | What is the ticket number, and what happened at 14:03? | NH-184. The request was put on hold. |
| callback.wav | What did the caller report, and what do they want checked? | The caller saw a recovery notice they did not request. They want to know whether recovery was put on hold. Open the transcript. |
| runbook.md | Which group handles this ticket? What is its phone number? | Identity Operations is named. No phone number is provided. Ask the questions separately to test both retrieval and abstention. |
| No attachment | Write a Python function that counts distinct ticket IDs in a list, and test it on a list with a duplicate. | Show the executed test result. |
| recovery-review.mp4 | What was the last action, and when did it happen? | Identity review opened at 14:04. Inspect the sampled frames to verify it. |

Use the team's own timing from a fresh rehearsal. For a second case, change the source material and keep it out of model or prompt development. Have a teammate check the result against the original, record the elapsed time and any error, and identify it as an internal rehearsal in the pitch.

## Logs: five planted intrusions

Build the file once on the presentation laptop (it needs `data/raw/wednesday.csv`; the output is git-ignored):

```text
.venv/bin/python tests/make_demo_intrusions.py
```

Attach `data/demo/campus_afternoon.csv` (6 MB). It holds two attack-free hours of CIC-IDS2017 Wednesday traffic, a day the detector never trained on, plus five synthetic intrusions we planted on fictional hosts. The detector is not tuned on this file.

| Planted intrusion | Expected incident |
|---|---|
| HTTP flood on the web server, 3 min | #1: one outside host, 1,000 alerts a minute on port 80 |
| Infected laptop sweeps port 445, then scans 1,000 ports | #2: one inside host, 253 targets, 1,000 ports |
| Password guessing on SSH, 25 min | #3: one outside host, port 22 only |
| The same laptop uploads ~1.5 GB to an outside host | #4: the same inside host as #2, 40 huge uploads on port 443 |

Last run: 58,861 connections → 4,714 alerts → 9 incidents in 8 s; all five intrusions are incidents #1–#4; 0.36% of normal connections alerted. Incidents #5–#9 are normal traffic flagged only by the anomaly score. Good follow-ups: "What is int-host-5 doing across incidents 2 and 4?" and "Is incident 5 an attack?"
