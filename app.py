from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, send, emit
from data_fetcher import fetch_data
import colorlog
import logging
import json
import requests
import csv
from bs4 import BeautifulSoup

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)s:%(message)s'))
logger = colorlog.getLogger('example')
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Initialize Flask application
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variable for current airport code
current_airport_code = None  
rooms = {}

def process_data(data):
    """
    Processes the data and emits it to the client
    """
    for room in rooms.keys():  # Loop over all rooms
        # Filter pilots based on current airport code
        pilots = [
            item
            for item in data.get('pilots', [])
            if (item.get("flight_plan") and item["flight_plan"].get("departure") or "")
            == room  # Use room here instead of a global current_airport_code
        ]

        # Emit data to the client
        socketio.emit('new_pilots', {'pilots': pilots}, room=room)
        callsigns = [pilot.get('callsign') for pilot in pilots]
        logger.info(f'Emitted new_pilots event to room {room}: {callsigns}')


def read_csv(departure, arrival):
    with open("prefroutes_db.csv", "r") as f:
        reader = csv.reader(f, quotechar=",")
        for row in reader:
            if row[0] == departure[1:] and row[2] == arrival[1:]:
                return row[1]
        return None


def get_airport_info(icao):
    # Make a request to the airport-data API
    api_url = f"https://www.airport-data.com/api/ap_info.json?icao={icao}"
    r = requests.get(api_url).json()
    airport_name = ""
    longitude = 0

    # Extract the airport name and longitude from the response
    try:
        airport_name = r["name"]
        longitude = r["longitude"]
    except:
        print("Error Getting Airport information. Code: 404")
    # Return a tuple containing the airport name and longitude
    return (airport_name, longitude)


def get_airport_data(airport_name):
    with open("data.json", "r") as f:
        # Load the JSON file into a Python object
        data = json.load(f)

    pilots = [
        item
        for item in data["pilots"]
        if (item.get("flight_plan") and item["flight_plan"].get("departure") or "")
        == airport_name
    ]
    selected_pilot = None
    route = ""
    valid_route = ""
    apt_info = ""
    name = ""
    longitude = ""
    alt_valid = ""
    call = ""
    if request.method == "POST":
        selected_callsign = request.form.get("callsign")
        if selected_callsign:
            for pilot in pilots:
                if pilot["callsign"] == selected_callsign:
                    selected_pilot = pilot
                    break
        if selected_pilot is not None:
            departure1 = selected_pilot["flight_plan"]["departure"]
            arrival1 = selected_pilot["flight_plan"]["arrival"]
            filed_route = selected_pilot["flight_plan"]["route"]
            altitude = selected_pilot["flight_plan"]["altitude"]
            alt_check = str(altitude)[:-3]
            alt_check = int(alt_check)
            route = read_csv(departure1, arrival1)
            if route is not None:
                route = route[4:]
                route = route[:-4]
                print(route)
                print(filed_route)
                if route == filed_route:
                    valid_route = "Route Valid"
                else:
                    valid_route = "Invalid"
            apt_info = get_airport_info(arrival1)
            name, longitude = apt_info
            longitude = float(longitude)
            depart_info = get_airport_info(departure1)
            dname, dlongitude = depart_info
            dlongitude = float(dlongitude)
            if longitude >= dlongitude:
                if alt_check % 2 == 0:
                    alt_valid = "Cruise Invalid"
                else:
                    alt_valid = "Cruise Valid"
            else:
                if alt_check % 2 == 0:
                    alt_valid = "Cruise Valid"
                else:
                    alt_valid = "Cruise Invalid"
            url = (
                "https://123atc.com/call-sign/" + selected_callsign[:3]
            )  # Replace with the actual website URL

            response = requests.get(url)
            html_content = response.text

            soup = BeautifulSoup(html_content, "html.parser")

            callsign_element = soup.select_one("table.term h2")
            if callsign_element:
                call = callsign_element.get_text()

    return pilots, selected_pilot, route, valid_route, name, alt_valid, call


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/airport/<airport_code>", methods=["GET", "POST"])
def airport_info(airport_code):
    global current_airport_code

    airport_code = airport_code.upper()

    # Update current airport code
    current_airport_code = airport_code
    logger.debug(f'Updated current airport code: {current_airport_code}')

    # Get airport data
    (
        pilots,
        selected_pilot,
        route,
        valid_route,
        name,
        alt_valid,
        call,
    ) = get_airport_data(airport_code)

    socketio.emit('new_pilots', {'pilots': pilots}, room=current_airport_code)
    rooms[airport_code] = set()  # create a new set for the room
    callsigns = [pilot.get('callsign') for pilot in pilots]
    logger.info(f'Emitted new_pilots event: {callsigns}')

    # Render template with fetched data
    return render_template(
        "airport.html",
        callsigns=pilots,
        selected_pilot=selected_pilot,
        route=route,
        valid_route=valid_route,
        name=name,
        alt_valid=alt_valid,
        call=call,
        airport_code=airport_code
    )

@socketio.on('fetch_initial_data')
def fetch_initial_data(data):
    room = data['room']
    fetch_data(process_data)

@socketio.on('connect')
def on_connect():
    logger.debug(f'Client connected: {request.sid}')

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    if room not in rooms:
        rooms[room] = set()
    rooms[room].add(request.sid)
    logger.debug(f'Client requested to join room: {room}')

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    rooms[room].remove(request.sid)
    if len(rooms[room]) == 0:
        del rooms[room]
    logger.debug(f'Client requested to leave room: {room}')

@socketio.on('disconnect')
def on_disconnect():
    for room in list(rooms.keys()):
        if request.sid in rooms[room]:
            rooms[room].remove(request.sid)
            if len(rooms[room]) == 0:
                del rooms[room]
            logger.warn(f'Client disconnected: {request.sid}')
            break


if __name__ == '__main__':
    # Start background task for fetching data and run the app
    socketio.start_background_task(fetch_data, process_data)
    socketio.run(app, host='0.0.0.0', port=5000)