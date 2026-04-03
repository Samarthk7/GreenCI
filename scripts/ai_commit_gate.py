#!/usr/bin/env python3
"""
GreenCI AI Commit Gatekeeper (v6 - Carbon-First + ML Advisory)

Behavior summary:
- If grid is dirty (>= GRID_DIRTY_THRESHOLD) -> BLOCK ALL (HOLD)
- Else: compute heuristic decision (size/tests/config)
  - If an ML model is present at scripts/models/model.pkl, call it to get prob_proceed
  - If model confident (>= ML_PROCEED_THRESH) -> override to PROCEED
  - If model confident (<= ML_HOLD_THRESH) -> override to HOLD
  - Otherwise keep heuristic decision
- Log everything (features, git, meta.ml.prob_proceed, meta.grid_intensity, digest)
"""

import sys
import os
import json
import hashlib
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

# ML
try:
    import joblib
except Exception:
    joblib = None

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
GRID_DIRTY_THRESHOLD = 350        # Above this = BLOCK ALL
MIN_LINES_CHANGED = 40
MIN_FILES_CHANGED = 2

INTENSITY_API_URL = "https://api.carbonintensity.org.uk/intensity"

LOG_DIR = os.path.join("scripts", "logs")
LOG_FILE = os.path.join(LOG_DIR, "ai_decisions.jsonl")

MODEL_PATH = os.path.join("scripts", "models", "model.pkl")
ML_PROCEED_THRESH = 0.85   # model probability >= this → override to PROCEED
ML_HOLD_THRESH = 0.15      # model probability <= this → override to HOLD

# ---------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------
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
    test_files_changed: int
    config_files_changed: int
    doc_files_changed: int

# ---------------------------------------------------------
# DIFF PARSER & FEATURE EXTRACTOR
# ---------------------------------------------------------
def parse_numstat(diff: str) -> List[FileChange]:
    changes = []
    for line in diff.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a_raw, r_raw, path = parts
        try: added = int(a_raw)
        except: added = 0
        try: removed = int(r_raw)
        except: removed = 0
        changes.append(FileChange(path, added, removed))
    return changes

def extract_features(changes: List[FileChange]) -> Features:
    total_added = sum(c.added for c in changes)
    total_removed = sum(c.removed for c in changes)
    total_changed = total_added + total_removed

    def is_test(path): return "test" in path.lower() or path.lower().endswith("_test.py")
    def is_config(path): return ".github/workflows" in path.lower() or "ci" in path.lower()
    def is_doc(path): return path.lower().endswith(".md") or path.lower().startswith("docs/")

    return Features(
        files_changed=len(changes),
        total_added=total_added,
        total_removed=total_removed,
        total_changed=total_changed,
        test_files_changed=sum(is_test(c.path) for c in changes),
        config_files_changed=sum(is_config(c.path) for c in changes),
        doc_files_changed=sum(is_doc(c.path) for c in changes),
    )

# ---------------------------------------------------------
# GRID INTENSITY
# ---------------------------------------------------------
def fetch_grid_intensity() -> int:
    """Fetch actual grid CO2 intensity (gCO2/kWh); fallback 250."""
    try:
        with urllib.request.urlopen(INTENSITY_API_URL, timeout=5) as r:
            data = json.loads(r.read().decode())
            item = data["data"][0]["intensity"]
            val = item.get("actual") or item.get("forecast")
            if val is not None:
                return int(val)
    except Exception:
        pass
    return 250

# ---------------------------------------------------------
# HEURISTIC DECISION (carbon-first policy)
# ---------------------------------------------------------
def heuristic_decide(features: Features, intensity: int) -> Tuple[str, str]:
    # 1. Dirty grid -> HOLD everything
    if intensity >= GRID_DIRTY_THRESHOLD:
        return ("HOLD", f"Grid CO₂ is high ({intensity} gCO₂/kWh) — blocking CI to save carbon.")

    # 2. When clean: tests/config always allowed
    if features.test_files_changed > 0:
        return ("PROCEED", "Test files changed -> CI required.")
    if features.config_files_changed > 0:
        return ("PROCEED", "CI/config changed -> pipeline integrity required.")

    # 3. Size check
    if (features.total_changed >= MIN_LINES_CHANGED) or (features.files_changed >= MIN_FILES_CHANGED):
        return ("PROCEED", f"Significant change ({features.total_changed} lines across {features.files_changed} files).")

    # 4. Small -> HOLD
    return ("HOLD", f"Change is small ({features.total_changed} lines). Batch commits to reduce CI overhead.")

# ---------------------------------------------------------
# GIT CONTEXT & DIGEST
# ---------------------------------------------------------
def get_git_context():
    import subprocess
    def run(cmd):
        try:
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        except:
            return ""
    return {
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": run(["git", "rev-parse", "HEAD"]),
        "upstream": run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]),
    }

def compute_digest(features: Features, git_ctx: dict, intensity: int) -> str:
    raw = f"""
    {git_ctx.get('commit')}
    {git_ctx.get('upstream')}
    {features.files_changed}
    {features.total_changed}
    {intensity}
    """
    return hashlib.sha256(raw.encode()).hexdigest()

# ---------------------------------------------------------
# ML MODEL LOADING & PREDICTION (advisory)
# ---------------------------------------------------------
def load_ml_model():
    """Load model.pkl if available and joblib is installed; return model or None."""
    if joblib is None:
        return None
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        model = joblib.load(MODEL_PATH)
        return model
    except Exception:
        return None

def featurize_for_model(features: Features):
    """Return feature vector in same order used for training scripts/train_ml.py"""
    return [
        features.files_changed,
        features.total_added,
        features.total_removed,
        features.total_changed,
        features.test_files_changed,
        features.config_files_changed,
        features.doc_files_changed,
        0.0  # placeholder for intensity (we'll set later per-record)
    ]

def predict_ml_prob(model, features: Features, intensity_value: float = None):
    """
    Return probability that model predicts PROCEED (float 0..1).
    If model doesn't support predict_proba, return None.
    """
    if model is None:
        return None
    try:
        x = featurize_for_model(features)
        if intensity_value is not None:
            x[-1] = float(intensity_value)
        import numpy as np
        arr = np.array([x], dtype=float)
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(arr)[0]
            # assume positive class = 1 = PROCEED is second column if two-class
            if probs.shape[0] == 2:
                return float(probs[1])
            # fallback: return max
            return float(max(probs))
        else:
            # some models may expose decision_function or predict; we avoid using predict as probability
            return None
    except Exception:
        return None

# ---------------------------------------------------------
# LOGGING WITH DEDUP
# ---------------------------------------------------------
def log_decision(features, decision, explanation, intensity, ml_prob):
    os.makedirs(LOG_DIR, exist_ok=True)
    git_ctx = get_git_context()
    digest = compute_digest(features, git_ctx, intensity)

    # dedup check (recent lines)
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                last_lines = f.readlines()[-50:]
                for line in reversed(last_lines):
                    try:
                        old = json.loads(line)
                        if old.get("digest") == digest:
                            return
                    except:
                        continue
        except:
            pass

    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "digest": digest,
        "decision": decision,
        "explanation": explanation,
        "features": {
            "files_changed": features.files_changed,
            "total_added": features.total_added,
            "total_removed": features.total_removed,
            "total_changed": features.total_changed,
            "test_files_changed": features.test_files_changed,
            "config_files_changed": features.config_files_changed,
            "doc_files_changed": features.doc_files_changed,
        },
        "git": git_ctx,
        "meta": {
            "grid_intensity_g_per_kwh": intensity,
            "ml": {
                "model_present": os.path.exists(MODEL_PATH),
                "prob_proceed": ml_prob
            },
            "version": "v6-carbon-ml-advisory"
        }
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    diff = sys.stdin.read()
    if not diff.strip():
        print("[GreenCI] No diff -> Allow push.")
        sys.exit(0)

    changes = parse_numstat(diff)
    features = extract_features(changes)

    intensity = fetch_grid_intensity()

    # heuristic decision (carbon-first)
    h_decision, h_reason = heuristic_decide(features, intensity)

    # Load ML model (if any) and get prob
    model = load_ml_model()
    ml_prob = None
    if model is not None:
        # Provide intensity as last feature for model input if desired
        ml_prob = predict_ml_prob(model, features, intensity_value=intensity)

    # Apply ML advisory overrides conservatively
    final_decision = h_decision
    final_reason = h_reason
    override_note = ""
    if ml_prob is not None:
        # Print advisory info
        print(f"[GreenCI ML] prob_proceed = {ml_prob:.3f}")

        if ml_prob >= ML_PROCEED_THRESH and h_decision == "HOLD":
            final_decision = "PROCEED"
            override_note = f"(Overridden by ML: prob_proceed {ml_prob:.3f} >= {ML_PROCEED_THRESH})"
            final_reason = f"{h_reason} {override_note}"
        elif ml_prob <= ML_HOLD_THRESH and h_decision == "PROCEED":
            final_decision = "HOLD"
            override_note = f"(Overridden by ML: prob_proceed {ml_prob:.3f} <= {ML_HOLD_THRESH})"
            final_reason = f"{h_reason} {override_note}"
        else:
            # no override; still include probability in logs
            final_reason = f"{h_reason} (ML advisory: prob_proceed={ml_prob:.3f})"
    else:
        # no model present or failed
        final_reason = f"{h_reason} (ML advisory unavailable)"

    # Print summary
    print("\n=== GreenCI AI Commit Gate (v6 - Carbon + ML Advisory) ===")
    print(f"Grid intensity      : {intensity} gCO2/kWh")
    print(f"Files changed       : {features.files_changed}")
    print(f"Lines added         : {features.total_added}")
    print(f"Lines removed       : {features.total_removed}")
    print(f"Total lines changed : {features.total_changed}")
    print("------------------------------------")
    print(f"Heuristic decision  : {h_decision} -- {h_reason}")
    if ml_prob is not None:
        print(f"ML prob_proceed     : {ml_prob:.3f}")
    else:
        print("ML prob_proceed     : (no model)")

    print("------------------------------------")
    print(f"FINAL DECISION      : {final_decision}")
    print(f"FINAL REASON        : {final_reason}")
    print("====================================\n")

    # Log decision (dedup inside)
    log_decision(features, final_decision, final_reason, intensity, ml_prob)

    if final_decision == "PROCEED":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
