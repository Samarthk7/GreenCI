import os
import json
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report
from sklearn.metrics import accuracy_score
import joblib
import random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "logs", "ai_decisions.jsonl")
MODEL_PATH = os.path.join(HERE, "models", "model.pkl")

def load_data():
    X = []
    y = []

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            for line in f:
                row = json.loads(line)

                intensity = row.get("meta", {}).get("grid_intensity_g_per_kwh", random.randint(80, 400))
                lines_changed = random.randint(1, 100)
                files_changed = random.randint(1, 10)
                co2 = random.uniform(0.1, 2.0)

                decision = row.get("decision", "PROCEED")

                X.append([intensity, lines_changed, files_changed, co2])
                y.append(1 if decision == "PROCEED" else 0)

    # ---- Synthetic balancing ----
    proceed_count = sum(1 for label in y if label == 1)
    hold_count = sum(1 for label in y if label == 0)

    if hold_count == 0:
        print("Generating synthetic HOLD samples...")
        for _ in range(proceed_count):
            intensity = random.randint(350, 450)  # dirty grid
            lines_changed = random.randint(1, 5)  # tiny commit
            files_changed = random.randint(1, 2)
            co2 = random.uniform(0.5, 2.0)

            X.append([intensity, lines_changed, files_changed, co2])
            y.append(0)

    return np.array(X), np.array(y)


def main():
    X, y = load_data()

    print("Class distribution:", {0: sum(y==0), 1: sum(y==1)})

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )

    model = MLPClassifier(
        hidden_layer_sizes=(32, 16),
        activation='relu',
        solver='adam',
        max_iter=500,
        random_state=42
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    print("\nTraining Results:")
    print(classification_report(y_test, y_pred))

    acc = accuracy_score(y_test, y_pred)

    meta = {
        "accuracy": float(acc),
        "architecture": "MLP (32,16)",
        "activation": "ReLU"
    }

    meta_path = os.path.join(HERE, "models", "model_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f)

    os.makedirs(os.path.join(HERE, "models"), exist_ok=True)
    joblib.dump((model, scaler), MODEL_PATH)

    print(f"Saved neural network model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
