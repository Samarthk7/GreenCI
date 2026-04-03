#!/usr/bin/env python3
import os, joblib, json
MODEL = os.path.join("scripts", "models", "model.pkl")
if not os.path.exists(MODEL):
    print("Model missing:", MODEL)
    raise SystemExit(1)

m = joblib.load(MODEL)
print("Loaded model:", type(m))
# Build a dummy feature vector similar to training
x = [[2, 50, 10, 60, 0, 0, 0, 120.0]]
try:
    prob = m.predict_proba(x)[0][1]
    print("Model prob_proceed for sample:", prob)
except Exception as e:
    print("Model loaded but cannot predict_proba:", e)
