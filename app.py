from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
import math
import time
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "bloodbridge_secret_key"

DATABASE = "bloodbridge.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            blood_group TEXT NOT NULL,
            location TEXT NOT NULL,
            role TEXT NOT NULL,
            availability TEXT DEFAULT 'Available',
            latitude REAL,
            longitude REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blood_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            blood_group TEXT NOT NULL,
            units INTEGER NOT NULL,
            hospital TEXT NOT NULL,
            location TEXT NOT NULL,
            urgency TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            latitude REAL,
            longitude REAL,
            accepted_by INTEGER
        )
    """)

    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN availability TEXT DEFAULT 'Available'"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN latitude REAL"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN longitude REAL"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE blood_requests ADD COLUMN latitude REAL"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE blood_requests ADD COLUMN longitude REAL"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE blood_requests ADD COLUMN accepted_by INTEGER"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


# =========================================================
# GEOCODING
# =========================================================

def geocode_location(search_text):

    try:
        url = "https://nominatim.openstreetmap.org/search"

        params = {
            "q": search_text ,
            "format": "json",
            "limit": 1
        }

        headers = {
            "User-Agent": "BloodBridge/1.0 (student project)"
        }

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=5
        )


        response.raise_for_status()

        data = response.json()

        if data:
            return (
                float(data[0]["lat"]),
                float(data[0]["lon"])
            )

    except Exception as e:
        print("Geocoding error:", e)

    return None, None


# =========================================================
# UPDATE MISSING COORDINATES
# =========================================================

def update_missing_coordinates():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, location
        FROM users
        WHERE latitude IS NULL
        OR longitude IS NULL
    """)

    users = cursor.fetchall()

    for user in users:
        print("Updating user location:", user["location"])

        lat, lon = geocode_location(user["location"])

        if lat is not None and lon is not None:
            cursor.execute("""
                UPDATE users
                SET latitude = ?,
                    longitude = ?
                WHERE id = ?
            """, (lat, lon, user["id"]))

            conn.commit()

        time.sleep(1.1)

    cursor.execute("""
        SELECT id, hospital, location
        FROM blood_requests
        WHERE latitude IS NULL
        OR longitude IS NULL
    """)

    blood_requests = cursor.fetchall()

    for req in blood_requests:
        print(
            "Updating blood request location:",
            req["hospital"],
            req["location"]
        )

        search_text = req["hospital"] + ", " + req["location"]

        lat, lon = geocode_location(search_text)

        if lat is not None and lon is not None:
            cursor.execute("""
                UPDATE blood_requests
                SET latitude = ?,
                    longitude = ?
                WHERE id = ?
            """, (lat, lon, req["id"]))

            conn.commit()

        time.sleep(1.1)

    conn.close()
    print("Missing coordinates update completed.")


# =========================================================
# DISTANCE CALCULATION
# =========================================================

def calculate_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None

    R = 6371

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return round(R * c, 1)


# =========================================================
# BLOOD COMPATIBILITY
# =========================================================

COMPATIBILITY = {
    "A+": ["A+", "A-", "O+", "O-"],
    "A-": ["A-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "AB+": [
        "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"
    ],
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+": ["O+", "O-"],
    "O-": ["O-"]
}


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        blood_group = request.form["blood_group"]
        location = request.form["location"]
        role = request.form["role"]

        hashed_password = generate_password_hash(password)

        latitude, longitude = geocode_location(location)

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    blood_group,
                    location,
                    role,
                    availability,
                    latitude,
                    longitude
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                email,
                hashed_password,
                blood_group,
                location,
                role,
                "Available",
                latitude,
                longitude
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "Email already registered."

        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user:
            password_correct = False

            try:
                password_correct = check_password_hash(
                    user["password"],
                    password
                )
            except (ValueError, TypeError):
                password_correct = False

            if password_correct:
                session.clear()
                session["user_id"] = user["id"]

                return redirect(url_for("dashboard"))

        return "Invalid email or password."

    return render_template("login.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if not user:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    blood_requests = []

    if user["role"] == "donor":
        availability = user["availability"]

        if availability != "Unavailable":
            compatible_groups = COMPATIBILITY.get(
                user["blood_group"],
                []
            )

            if compatible_groups:
                placeholders = ",".join(
                    ["?"] * len(compatible_groups)
                )

                query = f"""
                    SELECT
                        blood_requests.*,
                        users.name AS requester_name
                    FROM blood_requests
                    JOIN users
                        ON blood_requests.requester_id = users.id
                    WHERE blood_requests.status = 'Pending'
                    AND blood_requests.blood_group
                        IN ({placeholders})
                    AND blood_requests.requester_id != ?
                """

                rows = conn.execute(
                    query,
                    compatible_groups + [user["id"]]
                ).fetchall()

                for row in rows:
                    req = dict(row)

                    req["distance"] = calculate_distance(
                        user["latitude"],
                        user["longitude"],
                        req["latitude"],
                        req["longitude"]
                    )

                    blood_requests.append(req)

    blood_requests.sort(
        key=lambda x:
        x["distance"]
        if x["distance"] is not None
        else float("inf")
    )

    if user["role"] == "donor":
        accepted_rows = conn.execute("""
            SELECT
                blood_requests.*,
                users.name AS requester_name
            FROM blood_requests
            JOIN users
                ON blood_requests.requester_id = users.id
            WHERE blood_requests.status = 'Accepted'
            AND blood_requests.accepted_by = ?
            ORDER BY blood_requests.id DESC
        """, (user["id"],)).fetchall()

        accepted_requests = [
            dict(row)
            for row in accepted_rows
        ]
    else:
        accepted_requests = []

    if user["role"] != "donor":
        my_requests_rows = conn.execute("""
            SELECT
                blood_requests.*,
                users.name AS requester_name
            FROM blood_requests
            JOIN users
                ON blood_requests.requester_id = users.id
            WHERE blood_requests.requester_id = ?
            ORDER BY blood_requests.id DESC
        """, (user["id"],)).fetchall()

        my_requests = [
            dict(row)
            for row in my_requests_rows
        ]
    else:
        my_requests = []

    notification_count = len(blood_requests)

    conn.close()

    return render_template(
        "dashboard.html",
        user=user,
        blood_requests=blood_requests,
        accepted_requests=accepted_requests,
        my_requests=my_requests,
        notification_count=notification_count
    )


# =========================================================
# REQUEST BLOOD
# =========================================================

# Supports BOTH URLs:
# /request_blood
# /request-blood

@app.route("/request_blood", methods=["GET", "POST"])
@app.route("/request-blood", methods=["GET", "POST"])
def request_blood():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        blood_group = request.form["blood_group"]
        units = request.form["units"]
        hospital = request.form["hospital"]
        location = request.form["location"]
        urgency = request.form["urgency"]

        search_text = location + ", Rajasthan ,India" 

        latitude, longitude = geocode_location(search_text)

        conn = get_db()

        conn.execute("""
            INSERT INTO blood_requests
            (
                requester_id,
                blood_group,
                units,
                hospital,
                location,
                urgency,
                status,
                latitude,
                longitude,
                accepted_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            blood_group,
            units,
            hospital,
            location,
            urgency,
            "Pending",
            latitude,
            longitude,
            None
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("request_blood.html")


# =========================================================
# ACCEPT REQUEST
# =========================================================

@app.route("/accept/<int:request_id>")
def accept_request(request_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute("""
        SELECT id, role
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if not user or user["role"] != "donor":
        conn.close()
        return redirect(url_for("dashboard"))

    conn.execute("""
        UPDATE blood_requests
        SET
            status = 'Accepted',
            accepted_by = ?
        WHERE id = ?
        AND status = 'Pending'
    """, (
        user["id"],
        request_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# =========================================================
# DECLINE REQUEST
# =========================================================

@app.route("/decline/<int:request_id>")
def decline_request(request_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute("""
        SELECT id, role
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if not user or user["role"] != "donor":
        conn.close()
        return redirect(url_for("dashboard"))

    conn.execute("""
        UPDATE blood_requests
        SET
            status = 'Declined',
            accepted_by = NULL
        WHERE id = ?
        AND status = 'Pending'
    """, (request_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# =========================================================
# DONOR AVAILABILITY
# =========================================================

@app.route("/toggle_availability")
def toggle_availability():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute("""
        SELECT id, availability
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if user:
        if user["availability"] == "Available":
            new_status = "Unavailable"
        else:
            new_status = "Available"

        conn.execute("""
            UPDATE users
            SET availability = ?
            WHERE id = ?
        """, (
            new_status,
            user["id"]
        ))

        conn.commit()

    conn.close()

    return redirect(url_for("dashboard"))


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    init_db()

    # Uncomment the next line only if you want to update
    # missing latitude/longitude values:
    # update_missing_coordinates()

    app.run(debug=True)
