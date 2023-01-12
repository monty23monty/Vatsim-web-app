import json
import requests
import csv
from flask import Flask, render_template
from flask import request


app = Flask(__name__)


def read_csv(departure, arrival):
    with open("/home/19roberl/mysite/prefroutes_db.csv", "r") as f:
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
    airport_name = str(airport_name)
    with open("D:\code for IT\GUI - Copy\data.json", "r") as f:
        # Load the JSON file into a Python object
        data = json.load(f)

    pilots = [
        item
        for item in data["pilots"]
        if (item.get("flight_plan") and item["flight_plan"].get("departure") or "")
        == airport_name.upper()
    ]
    selected_pilot = None
    route = ""
    valid_route = ""
    apt_info = ""
    name = ""
    longitude = ""
    alt_valid = ""
    if request.method == "POST":
        selected_callsign = request.args.get("callsign")
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

    return pilots, selected_pilot, route, valid_route, name, alt_valid


@app.route("/adrain")
def adrain():
    return "<h1>Hello Adrain</h1>"


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/airport", methods=["GET", "POST"])
def airport_info():
    airport_name = request.form.get("airport")
    pilots, selected_pilot, route, valid_route, name, alt_valid = get_airport_data(
        airport_name
    )
    return render_template(
        "airport.html",
        callsigns=pilots,
        selected_pilot=selected_pilot,
        route=route,
        valid_route=valid_route,
        name=name,
        alt_valid=alt_valid,
    )


if __name__ == "__main__":
    app.run()