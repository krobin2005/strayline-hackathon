# Test results

Run 2026-11-18 20:54 on arm64 (macOS-26.3.1), models `qwen3-vl:8b` and `gemma4:e4b-it-q4_K_M` through Ollama, Wi-Fi not required.
Pack: `practice_pack` (100 items). Per-item answers stay local in `data/eval/` (pack rules).

| Input | Items | Correct | Needs review | Wrong / error | Accuracy (auto-scored) | Median s | Max s |
|---|---|---|---|---|---|---|---|
| image | 25 | 21 | 3 | 1 | 95% | 7.8 | 27.0 |
| audio | 20 | 11 | 9 | 0 | 100% | 7.2 | 10.3 |
| text | 20 | 18 | 2 | 0 | 100% | 5.1 | 8.1 |
| video | 15 | 2 | 13 | 0 | 100% | 62.5 | 95.7 |
| code | 20 | 19 | 0 | 1 | 95% | 18.5 | 38.0 |

**Overall: 71/100 correct automatically**; 27 free-form answers need a person to check.

How it's scored: see the docstring in `desk/eval.py`. Code uses the pack's own unit tests.

## Provisional review of the 27 "needs review" answers

The automatic scorer only marks an answer correct when it can prove it (an exact count, a whole-phrase match, or the unit tests). The 27 answers it couldn't prove were compared with the references by Claude, the AI coding assistant used to build this project, **not by a team member**. These verdicts are provisional until a teammate checks them. Item-level answers stay in git-ignored `data/eval/` per the pack's rules; only counts appear here.

| Input | Correct after provisional review | Remaining misses (kind of error) |
|---|---|---|
| image | 23/25 | one crowd count off by one (7 vs 6); a drink named by flavor rather than brand |
| audio | 18/20 | a fire heard only as "crackle"; ocean waves heard as a water vehicle |
| text | 20/20 | none (two correct answers were worded differently from the reference) |
| video | 13/15 | a bounce count; 8 squares appearing one at a time counted as 4 |
| code | 19/20 | one function failed the pack's unit tests |

**Provisional total: 93/100 (71/100 proven by the automatic scorer).**

Video takes about 60 s per clip. The 10–16 frames are sent as separate images, which costs about 10,500 tokens of image reading in Qwen3-VL. A single contact-sheet image was about 4× faster but scored 6/15 with 6 empty answers, so the sheet is only used to show the user which frames were sampled.
