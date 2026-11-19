# Test results

Run 2026-11-18 19:03 on arm64 (macOS-26.3.1), models `qwen3-vl:8b` and `gemma4:e4b-it-q4_K_M` through Ollama, Wi-Fi not required.
Pack: `practice_pack` (100 items). Per-item answers stay local in `data/eval/` (pack rules).

| Input | Items | Correct | Needs review | Wrong / error | Accuracy (auto-scored) | Median s | Max s |
|---|---|---|---|---|---|---|---|
| image | 25 | 23 | 0 | 2 | 92% | 11.5 | 33.6 |
| audio | 20 | 14 | 2 | 4 | 78% | 5.6 | 9.8 |
| text | 20 | 20 | 0 | 0 | 100% | 5.3 | 7.6 |
| video | 15 | 9 | 3 | 3 | 75% | 64.9 | 107.5 |
| code | 20 | 20 | 0 | 0 | 100% | 17.4 | 37.9 |

**Overall: 86/100 correct automatically**; 5 free-form answers need a person to check.

How it's scored: see the docstring in `desk/eval.py`. Code uses the pack's own unit tests.
