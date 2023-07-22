import requests
import eventlet
import json

def fetch_data(callback):
    while True:
        response = requests.get("https://data.vatsim.net/v3/vatsim-data.json")
        data = response.json()

        # Save data to a JSON file
        with open('data.json', 'w') as f:
            json.dump(data, f)
              # Filter data for the given room
        callback(data)
        eventlet.sleep(20)

