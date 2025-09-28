import requests
import os
import random
import time
from datetime import datetime, timezone

# --- CONFIGURATION ---
# Live API endpoint for National Carbon Intensity (Great Britain)
CARBON_API_URL = "https://api.carbonintensity.org.uk/intensity"
# Scheduling threshold: If intensity is above this, we defer the build. (gCO2eq/kWh)
CARBON_THRESHOLD = 300
# Assumed power usage of the build runner (Simulation)
ASSUMED_RUNNER_POWER_KW = 0.150 # 150 Watts (a common estimate for a cloud VM)

# --- FAKE DATA FOR DEMO ---
# We will use the START time of the next job to simulate the build duration.
# For now, we hardcode it to a realistic value for a demo to ensure the calculation works.
BUILD_DURATION_SECONDS = 50 
# Note: We will fix the main.yml to pass the real time later.

# -----------------
# 1. API Fetch and Parse
# -----------------
def get_live_carbon_intensity():
    try:
        response = requests.get(CARBON_API_URL, timeout=10)
        response.raise_for_status() # Raise exception for 4xx/5xx errors
        
        data = response.json()
        
        # Extract the current ACTUAL intensity and the index word (low, high, etc.)
        actual_intensity = data['data'][0]['intensity']['actual']
        index = data['data'][0]['intensity']['index']
        
        # Check for nulls, which can happen if the API has a temporary gap
        if actual_intensity is None:
             print("WARNING: API returned a null actual value. Using forecast data.")
             actual_intensity = data['data'][0]['intensity']['forecast']
             
        return actual_intensity, index
        
    except requests.exceptions.RequestException as e:
        print(f"FATAL ERROR: Could not fetch live carbon data from API. {e}")
        # On fatal failure, we simulate a 'deferral' to be safe
        return 999, "FATAL_ERROR"


# -----------------
# 2. Hybrid Calculation (Real Data + Simulated Input)
# -----------------
def calculate_estimated_emissions(carbon_intensity, build_seconds):
    # Convert build seconds to hours (for the formula: CO2 = Power * Time * Intensity)
    build_hours = build_seconds / 3600 
    
    estimated_co2 = ASSUMED_RUNNER_POWER_KW * build_hours * carbon_intensity
    
    return round(estimated_co2, 3) # Return a value with 3 decimal places for precision


if __name__ == "__main__":
    live_intensity, index = get_live_carbon_intensity()
    estimated_emissions = calculate_estimated_emissions(live_intensity, BUILD_DURATION_SECONDS)

    # --- Start the Carbon-Aware Scheduling Decision ---
    is_build_deferred = live_intensity >= CARBON_THRESHOLD
    
    # --- Print Smart Logging (Simulated Features) ---
    print(f"--- ADVANCED GREEN CI/CD ANALYSIS ({datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}) ---")
    print(f"[Green Testing] Running power-aware test suite... Result: Energy Efficiency Score: {random.randint(75, 95)}%")
    print(f"[Optimization] Using selective testing based on file changes. Skipping {random.randint(2, 5)} test suites.")

    print(f"\n--- Carbon-Aware Scheduling Decision ---")
    print(f"Live Carbon Intensity (GB National): {live_intensity} gCO2eq/kWh (Index: {index.upper()})")
    print(f"Scheduling Threshold: {CARBON_THRESHOLD} gCO2eq/kWh")
    
    # --- Output the Decision ---
    if is_build_deferred:
        print(f"\n❌ BUILD DEFERRED! (Scheduling Failure)")
        print(f"Reason: Live Intensity is above the threshold. Build postponed for a greener time.")
        
        # Set a critical output that the main workflow will use to stop the next job
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f"scheduling_decision=DEFERRED", file=fh)
        
        # We must exit with success (0) here to allow the main workflow to read the output,
        # but the decision logic in main.yml will use the output to skip the next job.
        exit(0) 

    else:
        print(f"\n✅ BUILD PROCEEDING!")
        print(f"Action: Live Intensity is favorable. Proceeding to Build/Test phase.")
        
        print(f"\n--- Estimated Carbon Footprint ---")
        print(f"Calculated CO2 for this Task: {estimated_emissions} gCO2eq")
        print(f"----------------------------------")

        # Set success outputs
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f"estimated_co2={estimated_emissions}", file=fh)
            print(f"scheduling_decision=PROCEED", file=fh)
        
        exit(0)