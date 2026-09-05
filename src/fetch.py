"""Fetch real-time departures from the Wiener Linien API and save the raw response.

Runs unattended on a schedule. Each run writes one timestamped JSON file to the
raw data layer, which is never modified afterwards; all cleaning happens
downstream so that transformation bugs can be fixed and re-run.

Data source: Stadt Wien - https://data.wien.gv.at
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Configuration -------------------------------------------------------

BASE_URL = "https://www.wienerlinien.at/ogd_realtime/monitor"

# Confirmed by testing in the browser: this API expects "rbl", not "stopId".
STOP_PARAM = "rbl"

# Platform IDs at Schottentor U (trams 37, 38, 40).
STOP_IDS = [18, 46, 1212, 1303, 1325]

REQUEST_TIMEOUT_SECONDS = 15

# Resolve paths relative to this file, so the script works no matter which
# directory it is launched from. This matters once a scheduler runs it.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
LOG_DIR = PROJECT_ROOT / "logs"


# --- Setup ---------------------------------------------------------------

def configure_logging():
    """Send log messages to both a file and the terminal.

    The file handler is the one that matters for scheduled runs, where nobody
    is watching the terminal.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "fetch.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


# --- Core steps ----------------------------------------------------------

def fetch_departures():
    """Call the Wiener Linien monitor endpoint for all configured stops.

    Returns:
        dict: The parsed JSON response.

    Raises:
        requests.RequestException: On any network or HTTP-level failure.
        ValueError: If the response body is not valid JSON.
    """
    # A list of tuples, not a dict, because the same key repeats once per
    # stop: ?rbl=18&rbl=46&rbl=1212&rbl=1303&rbl=1325
    query_params = [(STOP_PARAM, stop_id) for stop_id in STOP_IDS]

    response = requests.get(
        BASE_URL,
        params=query_params,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()

def save_raw_response(payload, fetched_at):
    """Write one API response to a timestamped JSON file in the raw layer.
    
    Args:
        payload (dict): The parsed API response, stored unmodified.
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

def count_monitors(payload):
    """Return how many platform monitors the response contained.
    
    Used only for a log message, so it must never raise:
    a surprising response
    shape should not bring down a collection run.
    """
    return len(payload.get("data", {}).get("monitors", []))

# Entry point
def main():
    """Fetch once, save the result and log out the outcome.
    
    Excepected failures are logged and swallowed rather than raised, because one
    failed run must not stop the scheduler from trying again in five minutes."""
    configure_logging()

    # UTC, not local time: Vienna's daylight-saving switch makes local
    # timestamps ambiguous for one hour every October.
    fetched_at = datetime.now(timezone.utc)

    try:
        payload = fetch_departures()
    except requests.exceptions.Timeout:
        logging.error("Request timed out after %s seconds", REQUEST_TIMEOUT_SECONDS)
        return
    except requests.exceptions.RequestException as error:
        logging.error("Request failed: %s", error)
        return
    except ValueError as error:
        logging.error("Response was not valid JSON: %s", error)
        return

    try:
        output_path = save_raw_response(payload, fetched_at)
    except OSError as error:
        logging.error("Could not write file: %s", error)
        return

    logging.info("Saved %s (%d monitors)", output_path.name, count_monitors(payload))


if __name__ == "__main__":
    main()
