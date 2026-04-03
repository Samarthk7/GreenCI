#!/usr/bin/env python3
"""
GreenCI API server (AI + Carbon + Dashboard)
Upgraded with Neural Network (MLP) model + Demo Mode
"""

import os
import json
import time
import joblib
import random
from typing import List, Dict, Any, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests

# ---------------- Paths ----------------
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(HERE, "logs", "ai_decisions.jsonl")
STATIC_DIR = os.path.join(HERE, "static")
MODEL_PATH = os.path.abspath(os.path.join(HERE, "models", "model.pkl"))
print("MODEL PATH:", MODEL_PATH)
print("MODEL EXISTS:", os.path.exists(MODEL_PATH))
app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)

# ---------------- Config ----------------
ASSUMED_RUNNER_POWER_KW = 0.150
DEFAULT_GRID_INTENSITY_G_PER_KWH = 250.0
INTENSITY_CACHE_TTL_SECONDS = 60
CARBON_API_BASE = "https://api.carbonintensity.org.uk"
GRID_DIRTY_THRESHOLD = 350
AI_THRESHOLD = 0.6

DEMO_MODE = False  # Toggle for simulation mode

_intensity_cache = {"value": None, "ts": 0}

# ---------------- Load AI Model ----------------
model = None
scaler = None

if os.path.exists(MODEL_PATH):
    model, scaler = joblib.load(MODEL_PATH)
    print("✅ Neural Network model loaded successfully.")
else:
    print("⚠ Model file not found. Run train_ml.py first.")

# ---------------- Helper Functions ----------------

def read_log_records() -> List[Dict[str, Any]]:
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line.strip()))
            except:
                continue
    return records


def fetch_current_grid_intensity() -> Optional[float]:
    if DEMO_MODE:
        return random.randint(350, 450)  # Dirty simulation

    try:
        url = f"{CARBON_API_BASE}/intensity"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        if isinstance(data.get("data"), list) and len(data["data"]) > 0:
            item = data["data"][0]
            intensity = item["intensity"]
            val = intensity.get("actual") or intensity.get("forecast")
            return float(val)
    except:
        return None
    return None


def get_cached_intensity() -> float:
    now = time.time()
    if _intensity_cache["value"] and (now - _intensity_cache["ts"]) < INTENSITY_CACHE_TTL_SECONDS:
        return _intensity_cache["value"]

    val = fetch_current_grid_intensity()
    if val is None:
        val = DEFAULT_GRID_INTENSITY_G_PER_KWH

    _intensity_cache["value"] = val
    _intensity_cache["ts"] = now
    return val


def predict_commit(intensity, lines_changed, files_changed, co2):
    if model is None or scaler is None:
        return 0.5

    features = [intensity, lines_changed, files_changed, co2]
    features_scaled = scaler.transform([features])
    prob = model.predict_proba(features_scaled)[0][1]
    return float(prob)


def estimate_co2_saved(intensity, seconds=300):
    hours = seconds / 3600.0
    return ASSUMED_RUNNER_POWER_KW * hours * intensity


def generate_explanation(intensity, lines, files, prob, decision):
    return f"""
Grid Intensity: {intensity} gCO2/kWh.
Commit modified {lines} lines across {files} files.
AI confidence (prob_proceed): {prob:.2f}.
Final Decision: {decision}.
"""


# ---------------- Routes ----------------

@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "dashboard.html")


@app.get("/api/demo/toggle")
def toggle_demo():
    global DEMO_MODE, _intensity_cache
    DEMO_MODE = not DEMO_MODE

    # Clear cache immediately
    _intensity_cache["value"] = None
    _intensity_cache["ts"] = 0

    return jsonify({"demo_mode": DEMO_MODE})


@app.get("/api/ai/push_status")
def push_status():
    intensity = get_cached_intensity()

    if intensity >= GRID_DIRTY_THRESHOLD:
        return jsonify({
            "allowed": False,
            "intensity_g_per_kwh": intensity,
            "reason": "Grid is dirty — pushes blocked."
        })

    return jsonify({
        "allowed": True,
        "intensity_g_per_kwh": intensity,
        "reason": "Grid clean — subject to AI decision."
    })

@app.get("/api/ai/model_info")
def model_info():
    meta_path = os.path.join(HERE, "models", "model_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            return jsonify(json.load(f))
    return jsonify({"accuracy": None})


@app.get("/api/ai/decisions/latest")
def latest():
    limit = int(request.args.get("limit", 10))
    records = read_log_records()[-limit:]

    decisions = []
    for idx, rec in enumerate(records, 1):
        decisions.append({
            "id": idx,
            "timestamp": rec.get("timestamp"),
            "decision": rec.get("decision"),
            "intensity_g_per_kwh": rec.get("meta", {}).get("grid_intensity_g_per_kwh"),
            "ml_prob": rec.get("meta", {}).get("ml", {}).get("prob_proceed"),
            "estimated_co2_g": rec.get("meta", {}).get("estimated_co2_saved"),
            "explanation": rec.get("explanation")
        })

    return jsonify({"decisions": decisions})


@app.get("/api/ai/decisions/summary")
def summary():
    records = read_log_records()
    proceed = sum(1 for r in records if r.get("decision") == "PROCEED")
    hold = sum(1 for r in records if r.get("decision") == "HOLD")

    total_saved = sum(
        r.get("meta", {}).get("estimated_co2_saved", 0)
        for r in records
        if r.get("decision") == "HOLD"
    )

    sustainability_score = min(100, int((hold / max(1, len(records))) * 100))

    return jsonify({
        "total_decisions": len(records),
        "proceed_count": proceed,
        "hold_count": hold,
        "estimated_carbon_saved_g": total_saved,
        "intensity_used_g_per_kwh": get_cached_intensity(),
        "sustainability_score": sustainability_score
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
