import pandas as pd
import glob
import os
import re
import urllib.parse
import urllib.request
import json
from typing import Optional, Tuple
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_location_name(file_name: str) -> Optional[str]:
    """
    Extracts and cleans the location name from a filename.
    """
    match = re.search(r'_-_\s*(.*)\.csv$', file_name)
    if not match:
        return None

    cleaned_name = match.group(1).replace('_', ' ')

    # Remove specified German words and 'OT'
    words_to_remove = [
        'wahlkreis', 'gemeinde', 'ortsteil', 'wahlbezirk', 'stimmbezirk',
        'briefwahlbezirk', 'amt', 'OT'
    ]

    for word in words_to_remove:
        # Use regex to find and remove the whole word, case-insensitively
        cleaned_name = re.sub(r'\b' + re.escape(word) + r'\b', '', cleaned_name, flags=re.IGNORECASE)

    # Clean numbers from output
    cleaned_name = re.sub(r'\d+', '', cleaned_name).strip()

    return cleaned_name.strip()

def geocode_location_blocking(location_name: str, api_key: str) -> Optional[Tuple[float, float]]:
    """
    Performs a blocking geocoding API call to geocode.maps.co.

    Returns a tuple of (latitude, longitude) or None on failure.
    """
    base_url = "https://geocode.maps.co/search"
    encoded_address = urllib.parse.quote_plus(location_name)
    # Append the country code to improve geocoding accuracy
    geocode_url = f"{base_url}?q={encoded_address}&countrycodes=de&api_key={api_key}"

    try:
        logging.info(f"Geocoding '{location_name}'...")
        with urllib.request.urlopen(geocode_url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data and isinstance(data, list) and len(data) > 0:
            first_result = data[0]
            if 'lat' in first_result and 'lon' in first_result:
                lat = float(first_result['lat'])
                lon = float(first_result['lon'])
                return (lat, lon)

        logging.warning(f"No results found for '{location_name}'.")
        return None

    except urllib.error.HTTPError as e:
        logging.error(f"HTTP error during geocoding for '{location_name}': {e.code} - {e.reason}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during geocoding '{location_name}': {e}")
        return None

def is_in_brandenburg(lat: float, lon: float) -> bool:
    """
    Checks if the given coordinates are within the approximate bounding box of Brandenburg.
    """
    # Approximate geographic bounding box for Brandenburg, Germany
    lat_min, lat_max = 51.1987, 53.5985
    lon_min, lon_max = 10.6653, 15.3313

    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

async def main(folder_path: str):
    """
    Main function to orchestrate the geocoding process.
    """
    api_key = os.getenv("GEOCODE_API_KEY")
    if not api_key:
        logging.error("GEOCODE_API_KEY environment variable not set.")
        return

    output_dir = "static/data/locations"
    os.makedirs(output_dir, exist_ok=True)

    all_files = glob.glob(os.path.join(folder_path, "*.csv"))

    # Filter for files with a 16-digit number (polling places)
    polling_place_files = [f for f in all_files if re.search(r'\d{16}', os.path.basename(f))]

    if not polling_place_files:
        logging.info("No polling place files found with a 16-digit ID.")
        return

    logging.info(f"Found {len(polling_place_files)} polling place files to process.")

    for file_path in polling_place_files:
        base_name = os.path.basename(file_path)

        # Extract the 16-digit ID
        match = re.search(r'(\d{16})', base_name)
        if not match:
            continue

        polling_place_id = match.group(1)
        location_name = clean_location_name(base_name)

        if not location_name:
            logging.warning(f"Could not extract location name from {base_name}. Skipping.")
            continue

        # Geocode the location
        lat_lon = await asyncio.to_thread(geocode_location_blocking, location_name, api_key)

        if lat_lon:
            lat, lon = lat_lon

            # Check if the location is within Brandenburg's boundaries
            if is_in_brandenburg(lat, lon):
                # Save to a new CSV file
                output_file = os.path.join(output_dir, f"{polling_place_id}.csv")
                try:
                    # Create a DataFrame to save the data
                    data_to_save = pd.DataFrame([{'name': location_name, 'lat': lat, 'lon': lon}])
                    data_to_save.to_csv(output_file, index=False)
                    logging.info(f"✅ Successfully geocoded and saved '{location_name}' to {output_file}")
                except Exception as e:
                    logging.error(f"❌ Failed to save data for {polling_place_id}: {e}")
            else:
                logging.warning(f"⚠️ Geocoded location '{location_name}' is outside of Brandenburg. Skipping save.")
        else:
            logging.warning(f"❌ Skipping save for {base_name} due to geocoding failure.")

        # Add a small delay to respect API rate limits
        await asyncio.sleep(1)

if __name__ == "__main__":
    # Change 'results' to the path of your CSV folder
    csv_folder = 'results'
    asyncio.run(main(csv_folder))
