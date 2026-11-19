# Strayline Desk handoff for the team and Claude

Updated Thursday, November 19, 2026. The latest app changes are on the working repo's `main`. The repo is public and was submitted to the organizers on Nov 19. The immediate priority is a timed offline rehearsal.

## What shipped

- `840b64c` restored separate video frames for inference and kept the contact sheet as visible evidence. Separate frames scored **13/15 on provisional review**, with a **62.5 s median** and **95.7 s max**. The faster contact-sheet inference trial scored **6/15**, with six empty answers. Keep the current models and video path for judging.
- `e33cd79` fixed Enter submitting during an upload or active response. It also changed the benchmark table to verified counts and review counts. The focused checks and all 13 unit tests passed.
- `6b54992` made evidence panels open by default. They remain collapsible. The rendering check passed, and a localhost API smoke check confirmed the runbook returned the correct group and supporting passage. The server was started in laptop-only mode for that check.

## Submission and rehearsal

1. **Submission: done.** The organizers asked each team to submit its own public repo through a Google Form instead of an IEEE org repo. This repo was made public and submitted on Nov 19 (team Bates Alpine). Push any last fixes to `main` before Thursday EOD and tag the final commit `final`. Friday is for presentations.
2. **Use the team's existing cybersecurity assets in the live pitch.** Walk through one campus IT case and show all five required inputs. Use the source evidence to explain the analyst's next action. Start the video early and explain local processing while it runs. Save the full network-log replay for the final if it crowds the first round. See [the timed script](PLAN.md#6-the-5-minute-round-1-pitch).
3. **Use the organizers' practice pack for benchmark evidence.** Show **76/100 automatically verified** and clearly label **95/100 after provisional AI review**. The second AI check of the 15 saved video outputs found 12 clearly correct, two counting misses, and one borderline answer about whether two shapes touched. A teammate can confirm the provisional grades. Run any judge-provided files through the same app.
4. **Rehearse on the presentation laptop without internet.** Start Ollama and Strayline before the test. Time the full five-minute pitch, including uploads and answers. Ask one question the runbook answers and one it doesn't. If a teammate times a campus IT task, label the result as an internal rehearsal. Use an offline local network for the optional phone demo. Keep a backup recording available and identify it as a recording if shown.

Keep remaining changes small. Fix issues exposed in rehearsal, reuse the existing assets, and keep per-item practice-pack answers local. See [recorded results](results/test_results.md) and [setup instructions](README.md#8-setup-and-run).
