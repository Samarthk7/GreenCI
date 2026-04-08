from flask import Flask, jsonify, request
import random
import datetime
import psutil

app = Flask(__name__)

# ------------------------------
# Utility Functions
# ------------------------------

def calculate_system_load():
    return round(random.uniform(20.0, 85.0), 2)

def generate_build_id():
    return f"BUILD-{random.randint(1000,9999)}"

def simulate_processing_delay():
    return random.randint(1, 5)

# ------------------------------
# Routes
# ------------------------------

@app.route('/')
def home():
    return """
    <h1>🚀 Demo Development Application </h1>
    <p>This is a simulated application used to test GreenCI commit evaluation.</p>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "OK",
        "timestamp": str(datetime.datetime.now())
    })

@app.route('/status')
def status():
    return jsonify({"service": "running"})


@app.route('/metrics')
def metrics():
    return jsonify({
        "cpu_load": calculate_system_load(),
        "memory_usage": random.randint(512, 4096),
        "active_sessions": random.randint(5, 50)
    })

@app.route('/build', methods=['POST'])
def trigger_build():
    build_id = generate_build_id()
    delay = simulate_processing_delay()

    return jsonify({
        "build_id": build_id,
        "status": "Triggered",
        "estimated_completion_seconds": delay
    })

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        return jsonify({"message": "Configuration updated successfully"})
    return jsonify({
        "version": "1.0.0",
        "environment": "dev"
    })

# ------------------------------
# Application Entry
# ------------------------------

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
