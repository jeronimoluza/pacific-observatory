"""KNN-panel competence-mapping experiment.

Measures where cheap model labelers (Sonnet / Codex-gpt-5.5 / Gemini-flash-lite)
peel off the Opus line as item difficulty rises. Difficulty = entropy of the
KNN gold-neighbour leaf distribution (a free, zero-token signal). Each model does
grounded multiple-choice over the KNN candidate leaves + their official COICOP
notes, so an invented code is structurally impossible. Three stages:

  prep.py    -> eval_items.jsonl   (KNN candidates + difficulty per held-out item)
  panel.py   -> panel_labels.jsonl (each model's choice + confidence per item)
  analyze.py -> competence_map.csv (per-difficulty-bin accuracy + Opus-agreement)
"""
