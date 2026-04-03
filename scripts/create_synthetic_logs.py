#!/usr/bin/env python3
"""
Create synthetic ai_decisions.jsonl for initial training/demo.

Generates a balanced mix of HOLD and PROCEED records with realistic feature sets
and per-record grid intensity values. Safe to run repeatedly: it will overwrite
the existing logs file (back it up if you need).
"""

import os, json, random
from datetime import datetime, timedelta

OUT_DIR = os.path.join("scripts", "logs")
OUT_FILE = os.path.join(OUT_DIR, "ai_decisions.jsonl")

os.makedirs(OUT_DIR, exist_ok=True)

def make_record(decision, features, intensity, commit_id):
    ts = (datetime.utcnow() - timedelta(minutes=random.randint(0, 1440))).isoformat() + "Z"
    record = {
        "timestamp": ts,
        "digest": f"synthetic-{commit_id}",
        "decision": decision,
        "explanation": f"Synthetic record ({decision})",
        "features": features,
        "git": {
            "branch": "main",
            "commit": f"synthetic-commit-{commit_id}",
            "upstream": "origin/main"
        },
        "meta": {
            "grid_intensity_g_per_kwh": intensity,
            "ml": {
                "model_present": False,
                "prob_proceed": None
            },
            "version": "synthetic-v1"
        }
    }
    return record

def gen_examples(n_each=50):
    records = []
    # PROCEED examples (larger changes, lower intensity often)
    for i in range(n_each):
        total_changed = random.randint(50, 500)
        files_changed = random.randint(2, 10)
        features = {
            "files_changed": files_changed,
            "total_added": int(total_changed * 0.6),
            "total_removed": int(total_changed * 0.4),
            "total_changed": total_changed,
            "test_files_changed": 1 if random.random() < 0.2 else 0,
            "config_files_changed": 1 if random.random() < 0.1 else 0,
            "doc_files_changed": 0
        }
        intensity = random.randint(50, 220)  # relatively cleanish
        rec = make_record("PROCEED", features, intensity, f"p{i}")
        records.append(rec)

    # HOLD examples (small changes or dirty grid)
    for i in range(n_each):
        # mix of small changes and moderate changes but high intensity
        if random.random() < 0.6:
            total_changed = random.randint(0, 10)
            files_changed = 1
        else:
            total_changed = random.randint(15, 80)
            files_changed = random.randint(1, 3)
        features = {
            "files_changed": files_changed,
            "total_added": int(total_changed * 0.6),
            "total_removed": int(total_changed * 0.4),
            "total_changed": total_changed,
            "test_files_changed": 0,
            "config_files_changed": 0,
            "doc_files_changed": 1 if random.random() < 0.3 else 0
        }
        # often dirty
        intensity = random.randint(300, 600) if random.random() < 0.6 else random.randint(120, 280)
        rec = make_record("HOLD", features, intensity, f"h{i}")
        records.append(rec)

    random.shuffle(records)
    return records

def write_records(records):
    # Overwrite existing log file to keep things clean for training
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print("Wrote", len(records), "synthetic records to", OUT_FILE)

if __name__ == "__main__":
    recs = gen_examples(n_each=75)  # creates 150 records total
    write_records(recs)
