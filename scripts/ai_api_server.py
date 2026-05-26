#!/usr/bin/env python3
"""
GreenCI API server (AI + Carbon + Dashboard)
Upgraded with CPU metrics + batching visibility + stable APIs
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
import psutil  # 🔥 NEW

# ---------------- Paths ----------------
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(HERE, "logs", "ai_decisions.jsonl")
STATIC_DIR = os.path.join(HERE, "static")
MODEL_PATH = os.path.abspath(os.path.join(HERE, "models", "model.pkl"))

# 🔥 NEW: pending file path
PENDING_FILE = os.path.join(os.getcwd(), "pending_commits.json")

app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)

# ---------------- Config ----------------
ASSUMED_RUNNER_POWER_KW = 0.150
DEFAULT_GRID_INTENSITY_G_PER_KWH = 250.0
INTENSITY_CACHE_TTL_SECONDS = 60
CARBON_API_BASE = "https://api.carbonintensity.org.uk"
GRID_DIRTY_THRESHOLD = 350
AI_THRESHOLD = 0.6

DEMO_MODE = False

_intensity_cache = {"value": None, "ts": 0}

# ---------------- Load Model ----------------
model = None
scaler = None

if os.path.exists(MODEL_PATH):
    model, scaler = joblib.load(MODEL_PATH)
    print("✅ Model loaded")
else:
    print("⚠ Model not found")

# ---------------- Utilities ----------------

def read_log_records():
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                records.append(json.loads(line.strip()))
            except:
                continue
    return records


def load_pending():
    try:
        if not os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "w") as f:
                json.dump([], f)
            return []
        with open(PENDING_FILE) as f:
            return json.load(f)
    except:
        return []


def fetch_current_grid_intensity():
    if DEMO_MODE:
        return random.randint(350, 450)

    try:
        r = requests.get(f"{CARBON_API_BASE}/intensity", timeout=5)
        data = r.json()
        val = data["data"][0]["intensity"].get("actual") or 250
        return float(val)
    except:
        return DEFAULT_GRID_INTENSITY_G_PER_KWH


def get_cached_intensity():
    now = time.time()
    if _intensity_cache["value"] and now - _intensity_cache["ts"] < INTENSITY_CACHE_TTL_SECONDS:
        return _intensity_cache["value"]

    val = fetch_current_grid_intensity()
    _intensity_cache["value"] = val
    _intensity_cache["ts"] = now
    return val

# ---------------- Routes ----------------

@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "dashboard.html")


# 🔥 DEMO TOGGLE
@app.get("/api/demo/toggle")
def toggle_demo():
    global DEMO_MODE
    DEMO_MODE = not DEMO_MODE
    _intensity_cache["value"] = None
    return jsonify({"demo_mode": DEMO_MODE})


# 🔥 GRID STATUS
@app.get("/api/ai/push_status")
def push_status():
    intensity = get_cached_intensity()

    return jsonify({
        "allowed": intensity < GRID_DIRTY_THRESHOLD,
        "intensity_g_per_kwh": intensity
    })


# 🔥 MODEL INFO
@app.get("/api/ai/model_info")
def model_info():
    meta_path = os.path.join(HERE, "models", "model_meta.json")
    if os.path.exists(meta_path):
        return jsonify(json.load(open(meta_path)))
    return jsonify({"accuracy": None})


# 🔥 LATEST DECISIONS
@app.get("/api/ai/decisions/latest")
def latest():
    records = read_log_records()[-10:]

    return jsonify({
        "decisions": [
            {
                "timestamp": r.get("timestamp"),
                "decision": r.get("decision"),
                "ml_prob": r.get("meta", {}).get("ml", {}).get("prob_proceed"),
                "explanation": r.get("explanation")
            }
            for r in records
        ]
    })


# 🔥 SUMMARY (FIXED CARBON CALC)
@app.get("/api/ai/decisions/summary")
def summary():
    records = read_log_records()

    proceed = sum(r.get("decision") == "PROCEED" for r in records)
    hold = sum(r.get("decision") == "HOLD" for r in records)

    # 🔥 Better carbon estimation
    carbon_saved = sum(
        r.get("meta", {}).get("estimated_co2_saved", 5)
        for r in records if r.get("decision") == "HOLD"
    )

    return jsonify({
        "total_decisions": len(records),
        "proceed_count": proceed,
        "hold_count": hold,
        "estimated_carbon_saved_g": carbon_saved,
        "intensity_used_g_per_kwh": get_cached_intensity(),
        "sustainability_score": int((hold / max(1, len(records))) * 100)
    })


# 🔥 CPU METRICS (FIXED)
@app.get("/metrics")
def metrics():
    try:
        return jsonify({
            "cpu_percent": psutil.cpu_percent(interval=0.5)
        })
    except Exception as e:
        return jsonify({
            "cpu_percent": 0,
            "error": str(e)
        })


# 🔥 PENDING COMMITS API (NEW)
@app.get("/api/pending")
def pending():
    data = load_pending()
    return jsonify({
        "count": len(data),
        "items": data
    })


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)