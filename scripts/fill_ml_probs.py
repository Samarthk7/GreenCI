#!/usr/bin/env python3
"""
Load scripts/models/model.pkl and add ml.prob_proceed to existing
scripts/logs/ai_decisions.jsonl records (overwrites file).
"""
import os, json
import joblib
import numpy as np

LOG_FILE = os.path.join("scripts", "logs", "ai_decisions.jsonl")
MODEL_PATH = os.path.join("scripts", "models", "model.pkl")

if not os.path.exists(LOG_FILE):
    raise SystemExit("No log file at " + LOG_FILE)
if not os.path.exists(MODEL_PATH):
    raise SystemExit("No model at " + MODEL_PATH)

model = joblib.load(MODEL_PATH)
print("Loaded model:", MODEL_PATH)

def featurize_for_row(rec):
    f = rec.get("features", {})
    intensity = rec.get("meta", {}).get("grid_intensity_g_per_kwh", 0.0) or 0.0
    x = [
        f.get("files_changed", 0),
        f.get("total_added", 0),
        f.get("total_removed", 0),
        f.get("total_changed", 0),
        f.get("test_files_changed", 0),
        f.get("config_files_changed", 0),
        f.get("doc_files_changed", 0),
        float(intensity)
    ]
    return np.array([x], dtype=float)

out = []
with open(LOG_FILE, "r", encoding="utf-8") as fh:
    for line in fh:
        if not line.strip(): continue
        rec = json.loads(line)
        try:
            X = featurize_for_row(rec)
            if hasattr(model, "predict_proba"):
                p = float(model.predict_proba(X)[0][1])
            else:
                # fallback: use predict as 0/1
                p = float(model.predict(X)[0])
            # ensure meta/ml exists
            rec.setdefault("meta", {})
            rec["meta"].setdefault("ml", {})
            rec["meta"]["ml"]["model_present"] = True
            rec["meta"]["ml"]["prob_proceed"] = round(p, 4)
        except Exception as e:
            print("Warning: failed to predict for a row:", e)
            rec.setdefault("meta", {}).setdefault("ml", {})["prob_proceed"] = None
        out.append(rec)

# overwrite file (backup first)
bak = LOG_FILE + ".bak"
os.replace(LOG_FILE, bak)
with open(LOG_FILE, "w", encoding="utf-8") as fh:
    for r in out:
        fh.write(json.dumps(r) + "\n")

print("Updated", LOG_FILE, "and saved backup as", bak)
