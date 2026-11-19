# Test results

Full run 2026-11-18 20:54; audio and code rerun 2026-11-19 after two changes (sound answers name the source and action, using AudioSet parent categories; code gets up to two fix rounds). Combined with `--rescore`, later runs winning per item. All on arm64 (macOS-26.3.1), models `qwen3-vl:8b` and `gemma4:e4b-it-q4_K_M` through Ollama, Wi-Fi not required.
Pack: `practice_pack` (100 items). Per-item answers stay local in `data/eval/` (pack rules).

| Input | Items | Automatically verified | Needs review | Wrong / error | Median s | Max s |
|---|---|---|---|---|---|---|
| image | 25 | 21 | 3 | 1 | 7.8 | 27.0 |
| audio | 20 | 15 | 5 | 0 | 6.9 | 16.9 |
| text | 20 | 18 | 2 | 0 | 5.1 | 8.1 |
| video | 15 | 2 | 13 | 0 | 62.5 | 95.7 |
| code | 20 | 20 | 0 | 0 | 28.3 | 84.3 |

**Overall: 76/100 correct automatically**; 23 free-form answers need a person to check.

How it's scored: see the docstring in `desk/eval.py`. Code uses the pack's own unit tests.

## Provisional review of the 23 "needs review" answers

The automatic scorer only marks an answer correct when it can prove it (an exact count, a whole-phrase match, or the unit tests). The 23 answers it couldn't prove were compared with the references by Claude, the AI coding assistant used to build this project, **not by a team member**. These verdicts are provisional until a teammate checks them. Item-level answers stay in git-ignored `data/eval/` per the pack's rules; only counts appear here.

| Input | Correct after provisional review | Remaining misses (kind of error) |
|---|---|---|
| image | 23/25 | one crowd count off by one (7 vs 6); a drink named by flavor rather than brand |
| audio | 19/20 | ocean waves heard as a water vehicle or stream (the fire answer, "A crackle (Fire)", is counted as right but is awkward) |
| text | 20/20 | none (two correct answers were worded differently from the reference) |
| video | 13/15 | a bounce count; 8 squares appearing one at a time counted as 4 |
| code | 20/20 | none (all pass the pack's unit tests) |

**Provisional total: 95/100 (76/100 proven by the automatic scorer).** The audio change was designed while looking at these 20 clips, so its gain should be confirmed on sounds the prompts never saw.

Video takes about 60 s per clip. The 10–16 frames are sent as separate images, which costs about 10,500 tokens of image reading in Qwen3-VL. A single contact-sheet image was about 4× faster but scored 6/15 with 6 empty answers, so the sheet is only used to show the user which frames were sampled.
