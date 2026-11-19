# Next steps

Where we are (Wed Nov 18, evening): the app works end to end, offline, for all five inputs plus logs. The practice pack scores **86/100** (image 23/25, audio 14/20, text 20/20, video 9/15, code 20/20). Everything is on GitHub.

**Hard deadline: code must be in our IEEE GitHub repo by end of day Thursday Nov 19.** Write access is cut after that. Friday is presentations only, with no code changes.

Each item lists roughly how long it takes and what "done" looks like. Work top to bottom.

---

## Thursday morning (9:00–12:00): must-do

1. **Get our official repo.** (15 min)
   - Check email for a reply from Vedanshi or Shubham about the IEEE GitHub org repo. If there's nothing by 10 am, ask in person in classroom 136/137.
   - Move our history there: `git remote add official <url>` then `git push official main`.
   - Done when: our commits show up in the IEEE org repo.

2. **Make video faster.** (1 hour)
   - Right now each clip takes ~65 s because 10 frames cost ~10,500 tokens. Shrinking frames doesn't help.
   - Try: (a) 6 frames instead of 10–16; (b) tile 4 frames into one image (a 2×2 grid).
   - Rerun `python -m desk.eval --only video` and compare score and time.
   - Done when: under ~25 s per clip with the score no worse than 9/15.

3. **Make sound answers more specific.** (30 min)
   - The classifier says "Vehicle" when "Helicopter" is right behind it.
   - Tell the answer step to prefer the most specific label listed, and show the top 3 labels to the user.
   - Rerun `--only audio`.
   - Done when: helicopter, fire and sneezing come back by name.

4. **Fix the log briefing.** (30 min)
   - It calls normal incidents "suspicious". Tighten the prompt (base rates: most incidents are harmless) and test on Wednesday's logs.
   - Done when: incident #1 (the DoS flood) is called out, and the normal incidents below it aren't called attacks.

## Thursday midday (12:00–3:00): demo material and evidence

5. **Make our own demo files.** (1–2 hours, can run in parallel on a second laptop)
   - 3 phishing screenshots (mock emails we make ourselves; no real people's data).
   - A short incident-response runbook as a PDF (we write it; 2–3 pages).
   - 2 scam voicemails we record ourselves ("This is the IT help desk, have your password ready…").
   - 1 screen recording of a fake "tech support" pop-up (we make it).
   - Put them in `demo/` only if they contain no private data; otherwise keep them local.

6. **Time a team rehearsal.** One teammate plays the analyst with the [sample case](demo/README.md); another records completion time, evidence used, and any wrong answers. Identify this as an internal exercise on the impact slide.

7. **Phone test.** (15 min)
   - Start the app, open the printed phone address on a phone on the same Wi-Fi or hotspot, and try an image and a document.
   - Done when: it works on a phone (that's a judging bonus).

## Thursday afternoon (3:00–9:00): lock it down

8. **Final test run.** (40 min)
   - `.venv/bin/python -m desk.eval` on the full practice pack. This updates `results/test_results.md` for the slides.

9. **Clean-clone check.** (30 min)
   - On Liam's or Zac's laptop: clone the repo, run `sh setup.sh`, start the app, then run `tests/smoke_api.py`.
   - Done when: it works from scratch, which proves the README instructions.

10. **Code freeze at 9 pm.**
    - Last push to the IEEE repo. Tag it: `git tag final && git push official final`.
    - Nothing after this.

## Friday (no code): present

11. **Slides** (keep them short):
    - who it's for and their problem
    - live demo
    - architecture: two models plus a sound classifier plus the detector, and why each was chosen
    - hardware (M4 Pro, 24 GB)
    - test results table
    - limits
    - one measured outcome from the team rehearsal, labeled as such

12. **Rehearse the 5-minute pitch twice with Wi-Fi off.** Show all five inputs in about 3 minutes. The script is in PLAN.md §6.

13. **Prepare for questions:** why these models, what fails, how we stop it making things up, is the code sandbox safe, did you build this before. Answers are in PLAN.md §6.

14. **Before going on stage:**
    - Start the app a minute early, so the models load.
    - Charge the laptop and have a phone on the same hotspot.
    - Keep a backup screen recording of a full run, used only if the live demo fails, and say it's a recording.

---

## If we're behind

Cut in this order:
- the log detector polish (item 4)
- the phone test (item 7)
- the video speed-up (item 2): keep the slow version and say so as a named limit

Never cut a whole input type.
