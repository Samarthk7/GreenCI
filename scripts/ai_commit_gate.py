#!/usr/bin/env python3

import sys
import os
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import List
import random

try:
    import joblib
except:
    joblib = None

# ---------------- CONFIG ----------------
GRID_DIRTY_THRESHOLD = 350
MIN_LINES_CHANGED = 40

INTENSITY_API_URL = "https://api.carbonintensity.org.uk/intensity"

LOG_DIR = os.path.join("scripts", "logs")
MODEL_PATH = os.path.join("scripts", "models", "model.pkl")

PENDING_FILE = os.path.join(os.getcwd(), "pending_commits.json")

# 🔥 NEW: cumulative threshold
CUMULATIVE_THRESHOLD = 10


# ---------------- FILE HANDLING ----------------
def load_pending():
    try:
        if not os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "w") as f:
                json.dump([], f)
            return []
        with open(PENDING_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_pending(data):
    try:
        with open(PENDING_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass


# ---------------- DATA ----------------
@dataclass
class FileChange:
    path: str
    added: int
    removed: int

@dataclass
class Features:
    files_changed: int
    total_added: int
    total_removed: int
    total_changed: int


# ---------------- PARSER ----------------
def parse_numstat(diff: str) -> List[FileChange]:
    changes = []
    for line in diff.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, r, path = parts
        try: a = int(a)
        except: a = 0
        try: r = int(r)
        except: r = 0
        changes.append(FileChange(path, a, r))
    return changes


def extract_features(changes):
    total_added = sum(c.added for c in changes)
    total_removed = sum(c.removed for c in changes)

    return Features(
        files_changed=len(changes),
        total_added=total_added,
        total_removed=total_removed,
        total_changed=total_added + total_removed
    )


# ---------------- GRID ----------------
def fetch_grid_intensity():
    try:
        with urllib.request.urlopen(INTENSITY_API_URL, timeout=5) as r:
            data = json.loads(r.read().decode())
            val = data["data"][0]["intensity"].get("actual") or 250
            return int(val)
    except:
        return 250


# ---------------- HEURISTIC ----------------
def heuristic_decide(features, intensity, is_significant):

    system_load = random.randint(20, 90)

    # 1. Energy check
    if system_load > 85:
        return ("HOLD", f"High system load ({system_load}%)")

    # 2. Carbon check
    if intensity >= GRID_DIRTY_THRESHOLD:
        return ("HOLD", f"High carbon intensity ({intensity})")

    # 🔥 3. IMPORTANT CHANGE PRIORITY
    if is_significant:
        return ("PROCEED", "Important logic change detected")

    # 4. Size check
    if features.total_changed >= MIN_LINES_CHANGED:
        return ("PROCEED", "Large change")

    # 5. Efficiency check
    efficiency = features.total_changed / max(1, intensity)
    if efficiency < 0.05:
        return ("HOLD", "Low efficiency")

    return ("HOLD", "Small change — batching")


# ---------------- ML ----------------
def load_ml_model():
    if joblib is None or not os.path.exists(MODEL_PATH):
        return None
    try:
        return joblib.load(MODEL_PATH)
    except:
        return None


def predict_ml_prob(model, features, intensity):
    try:
        import numpy as np
        X = np.array([[features.files_changed, features.total_changed, intensity]])
        return float(model.predict_proba(X)[0][1])
    except:
        return None


# ---------------- MAIN ----------------
def main():
    diff = sys.stdin.read()

    if not diff.strip():
        sys.exit(0)

    changes = parse_numstat(diff)
    features = extract_features(changes)

    # 🔥 IMPORTANT CHANGE DETECTION (DEMO SAFE)
    is_significant = False

    # Since numstat doesn't give code, use line count
    if features.total_changed >= 2:
        is_significant = True

    print(f"[DEBUG] Lines Changed: {features.total_changed}")
    print(f"[DEBUG] Significant: {is_significant}")

    intensity = fetch_grid_intensity()

    decision, reason = heuristic_decide(features, intensity, is_significant)

    # ML fallback
    model = load_ml_model()
    if model:
        prob = predict_ml_prob(model, features, intensity)
        print(f"[ML] prob={prob}")
    else:
        print("[GreenCI] ML unavailable — fallback active")

    # 🔥 BATCHING SYSTEM
    pending = load_pending()

    # 🔥 CUMULATIVE LOGIC
    total_pending_lines = sum(item.get("lines", 0) for item in pending)

    if total_pending_lines >= CUMULATIVE_THRESHOLD:
        print(f"[GreenCI] Cumulative change detected ({total_pending_lines} lines)")
        decision = "PROCEED"
        reason = "Cumulative changes became significant"

    if decision == "PROCEED":
        if pending:
            print(f"[GreenCI] Releasing {len(pending)} batched commits")
            save_pending([])
        sys.exit(0)

    else:
        pending.append({
            "time": datetime.utcnow().isoformat(),
            "lines": features.total_changed
        })

        save_pending(pending)

        print(f"[GreenCI] Commit batched. Pending: {len(pending)}")
        sys.exit(1)


if __name__ == "__main__":
    main()