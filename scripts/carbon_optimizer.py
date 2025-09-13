import json
import os

def find_most_sustainable_region(data_file):
    """
    Finds the most sustainable cloud region based on carbon intensity.
    """
    try:
        with open(data_file, 'r') as f:
            regions_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {data_file} was not found.")
        return None

    if not regions_data:
        print("No region data found.")
        return None

    # Initialize with a high value to ensure the first region is selected
    most_sustainable_region = None
    min_carbon_intensity = float('inf')

    # Iterate through the regions to find the one with the lowest carbon intensity
    for region in regions_data:
        if region['carbon_intensity_g_co2_per_kwh'] < min_carbon_intensity:
            min_carbon_intensity = region['carbon_intensity_g_co2_per_kwh']
            most_sustainable_region = region

    return most_sustainable_region

if __name__ == "__main__":
    data_file_path = os.path.join(os.path.dirname(__file__), 'carbon_intensity_data.json')
    best_region = find_most_sustainable_region(data_file_path)

    if best_region:
        print("--- Carbon-Aware Deployment Optimizer Result ---")
        print(f"Optimal Cloud Region: {best_region['location']} ({best_region['provider']})")
        print(f"Optimal Region ID: {best_region['region']}")
        print(f"Estimated Carbon Intensity: {best_region['carbon_intensity_g_co2_per_kwh']} gCO2eq/kWh")
        print("---------------------------------------------")

        # This is the crucial part for GitHub Actions.
        # It sets an output variable that can be used by other steps in the pipeline.
        # This is how we make our 'plugin' work!
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f"optimal_region={best_region['region']}", file=fh)
            print(f"optimal_region_provider={best_region['provider']}", file=fh)
            print(f"optimal_carbon_intensity={best_region['carbon_intensity_g_co2_per_kwh']}", file=fh)