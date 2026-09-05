"""Fetch real-time departures from the Wiener Linien API and save the raw response.

Data source: Stadt Wien - https://data.wien.gv.at
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

# Configuration

BASE_URL = "https://www.wienerlinien.at/ogd_realtime/monitor"

# Confirmed by testing in the browser: this API expects "rbl", not "stopId".
STOP_PARAM = "rbl"

# Platform IDs at Schottentor U(trams 37, 38, 40)
STOP_IDS = [18, 46, 1212, 1303, 1325]

REQUEST_TIMEOUT_SECONDS = 15

# Resolve paths relative to this file, so the script works no matter which
# directory it is launched from. This matters once a scheduler runs it.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

# Functions
def fetch_departures():
    """Call the Wiener Linien monitor endpoint for all configured stops.
    
    Returns:
        dict: The parsed JSON response.
        
    Raises:
        requests.HTTPError: if the server returned an error status code.
        """
    # A list of tuples, not a dict, because the same key repeats once per stop
    # ?rbl=18&rbl=46&rbl=1212&rbl=1303&rbl=1325
    query_params = [(STOP_PARAM, stop_id) for stop_id in STOP_IDS]

    response = requests.get(
        BASE_URL,
        params=query_params,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status

def save_raw_response(payload, fetched_at):
    """Write one API response to a timestamped JSON file in the raw layer.
    
    Args:
        payload (dict): the parsed API response, stored unmodified.
        fetched_at (datetime): When the request was made, in UTC.
    
    Returns:
        Path: The file that was written.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Store our own fetch time alongside the payload so the file is
    # self-describing, even if the API's own serverTime is missing or odd.
    record = {
        "fetched_at_utc": fetched_at.isoformat(),
        "stop_ids": STOP_IDS,
        "payload": payload,
    }
    filename = f"monitor_{fetched_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path = RAW_DATA_DIR / filename
    output_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return output_path

# Entry point
def main():
    """Fetch once and save the result."""
    # UTC, not local time: Vienna's daylight-saving switch makes local
    # timestamps ambigous for one hour every October
    fetched_at = datetime.now(timezone.utc)

    payload = fetch_departures()
    output_path = save_raw_response(payload, fetched_at)

    print(f"Saved {output_path.name}")

if __name__ == "__main__":
    main()


