"""Test call to the Wiener Linien real-time departures API."""

import requests

BASE_URL = "https://www.wienerlinien.at/ogd_realtime/monitor"

response = requests.get(BASE_URL, params={"rbl":1212}, timeout=15)

print("Status code:", response.status_code)

print(response.text[:500])