"""Vehicle Dynamics Calculator — web frontend.

Flask backend that reuses the calculator logic from the
Vehicle-Dynamics-Calculator Python project as its backend.
"""
import math

from flask import Flask, render_template, request

from calculators import aero_drag, braking, power_to_weight_ratio, rpm_calculator
from database.mongo import cars_collection

app = Flask(__name__)

def get_all_cars():
    """Get all vehicle names from MongoDB."""
    return sorted(
        car["identity"]["name"]
        for car in cars_collection.find({}, {"identity.name": 1, "_id": 0})
        if "identity" in car and "name" in car["identity"]
    )

GITHUB_REPO = "https://github.com/tsiri1612/Vehicle-Dynamics-Calculator"


def github_file(path):
    """Build a GitHub blob link for a source file in the repo."""
    return f"{GITHUB_REPO}/blob/main/{path}"


def _arc_path(cx, cy, radius, a0, a1, steps=48):
    """SVG path for an arc from a0..a1 degrees, measured clockwise from up."""
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + radius * math.sin(a), cy - radius * math.cos(a)))
    d = "M {:.1f} {:.1f}".format(*pts[0])
    for px, py in pts[1:]:
        d += " L {:.1f} {:.1f}".format(px, py)
    return d


def build_tach():
    """Build the hero tachometer as an inline SVG string."""
    cx, cy, r = 130, 130, 100
    parts = []

    # outer track
    parts.append(
        f'<path d="{_arc_path(cx, cy, r, -120, 120)}" stroke="#1e1e1e" stroke-width="3" fill="none"/>'
    )
    # redline arc (7000-8000 rpm -> 90..120 deg)
    parts.append(
        f'<path d="{_arc_path(cx, cy, r, 90, 120)}" stroke="#e10600" stroke-width="5" fill="none" opacity="0.75"/>'
    )

    # ticks
    for a in range(-120, 121, 10):
        rad = math.radians(a)
        major = a % 30 == 0
        r1 = 78 if major else 90
        x1 = cx + r1 * math.sin(rad)
        y1 = cy - r1 * math.cos(rad)
        x2 = cx + r * math.sin(rad)
        y2 = cy - r * math.cos(rad)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#cfcfcf" stroke-width="{2.4 if major else 1.2}" opacity="0.9"/>'
        )

    # number labels at major ticks (0..8)
    for a in range(-120, 121, 30):
        rad = math.radians(a)
        x = cx + 64 * math.sin(rad)
        y = cy - 64 * math.cos(rad)
        val = int(round((a + 120) / 30))
        if abs(x - cx) < 6:
            anchor = "middle"
        elif x > cx:
            anchor = "start"
        else:
            anchor = "end"
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="#8a8a8a" font-family="Rajdhani, sans-serif" '
            f'font-size="14" font-weight="600" text-anchor="{anchor}" '
            f'dominant-baseline="central">{val}</text>'
        )

    # needle (initially at rest, 0 rpm) + center hub
    needle = (
        '<g id="tach-needle" transform="rotate(-120 130 130)">'
        '<polygon points="127.5,131 132.5,131 130,48" fill="#e10600"/>'
        '</g>'
    )
    hub = (
        '<circle cx="130" cy="130" r="6" fill="#050505" stroke="#e10600" stroke-width="2"/>'
        '<circle cx="130" cy="130" r="2.5" fill="#e10600"/>'
    )

    return (
        f'<svg class="tach" viewBox="0 0 260 200" aria-hidden="true">'
        + "".join(parts)
        + needle
        + hub
        + "</svg>"
    )


@app.route("/")
def index():
    calculators = [
        {
            "slug": "aero-drag",
            "tag": "WIND",
            "name": "Aerodynamic Drag",
            "desc": "Estimate drag force and the power required to overcome aerodynamic resistance using vehicle speed, drag coefficient, frontal area, and air density.",
            "file": "calculators/aero_drag.py",
        },
        {
            "slug": "braking",
            "tag": "STOP",
            "name": "Braking & Stopping",
            "desc": "Calculate reaction distance, braking distance, and total stopping distance across different road surfaces and driver conditions.",
            "file": "calculators/braking.py",
        },
        {
            "slug": "power-to-weight",
            "tag": "PWR",
            "name": "Power-to-Weight Ratio",
            "desc": "Compare horsepower per tonne and kilograms per horsepower to understand acceleration potential and overall vehicle performance.",
            "file": "calculators/power_to_weight_ratio.py",
        },
        {
            "slug": "rpm",
            "tag": "RPM",
            "name": "Engine RPM",
            "desc": "Compute engine RPM from vehicle speed, tyre diameter, gear ratio, and final drive ratio using drivetrain fundamentals.",
            "file": "calculators/rpm_calculator.py",
        },
    ]
    return render_template("index.html", calculators=calculators, github=GITHUB_REPO, tach=build_tach())


@app.route("/aero-drag", methods=["GET", "POST"])
def aero_drag_view():
    results = None
    error = None
    form = {"name": "", "cd": "", "area": "", "speed": ""}

    if request.method == "POST":
        form = {
            "name": request.form.get("vehicle", "").strip(),
            "cd": request.form.get("cd", "").strip(),
            "area": request.form.get("area", "").strip(),
            "speed": request.form.get("speed", "").strip(),
        }
        try:
            speed_kmh = float(form["speed"])

            if speed_kmh < 0:
                raise ValueError("Speed cannot be negative.")

            vehicle = cars_collection.find_one(
                {"identity.name": form["name"]},
                {"identity.name": 1, "aerodynamics": 1}
            )

            if vehicle:
                name = vehicle["identity"]["name"]

                aerodynamics = vehicle.get("aerodynamics", {})

                cd = aerodynamics.get("cd")
                area = aerodynamics.get("frontal_area_m2")

                if cd is None or area is None:
                    raise ValueError(
                        "This vehicle does not have aerodynamic data — "
                        "enter Cd and frontal area manually."
                    )

            else:
                if not form["cd"] or not form["area"]:
                    raise ValueError(
                        "Vehicle not in the database — "
                        "enter Cd and frontal area manually."
                    )

                cd = float(form["cd"])
                area = float(form["area"])
                name = form["name"] or "Custom vehicle"

                if cd <= 0 or area <= 0:
                    raise ValueError(
                        "Cd and frontal area must be greater than zero."
                    )

            drag_force, drag_power, _ = aero_drag.calculate_drag(
                speed_kmh, cd, area
            )

            results = {
                "vehicle": f"{name} · Cd {cd} · {area} m²",
                "primary_value": f"{drag_force:,.2f}",
                "primary_unit": "N",
                "primary_label": "Aerodynamic drag force",
                "rows": [
                    {
                        "label": "Speed",
                        "value": f"{speed_kmh:,.2f}",
                        "unit": "km/h"
                    },
                    {
                        "label": "Aerodynamic drag force",
                        "value": f"{drag_force:,.2f}",
                        "unit": "N"
                    },
                    {
                        "label": "Drag power",
                        "value": f"{drag_power:,.2f}",
                        "unit": "hp"
                    },
                ],
            }

        except (ValueError, KeyError) as exc:
            error = str(exc) or "Please check your inputs."

    return render_template(
        "aero_drag.html",
        results=results,
        error=error,
        form=form,
        cars=get_all_cars(),
        github=GITHUB_REPO,
        source=github_file("calculators/aero_drag.py"),
    )


@app.route("/braking", methods=["GET", "POST"])
def braking_view():
    results = None
    error = None
    form = {"speed": "", "road": "1", "driver": "1"}
    roads = braking.ROAD_CONDITIONS
    drivers = braking.DRIVER_CONDITIONS

    if request.method == "POST":
        form = {
            "speed": request.form.get("speed", "").strip(),
            "road": request.form.get("road", "1"),
            "driver": request.form.get("driver", "1"),
        }
        try:
            speed_kmh = float(form["speed"])
            if speed_kmh < 0:
                raise ValueError("Speed cannot be negative.")
            road = int(form["road"])
            driver = int(form["driver"])
            if road not in roads or driver not in drivers:
                raise ValueError("Invalid road or driver condition.")
            reaction, brake, stopping, road_label, driver_label = braking.calculate_stopping(speed_kmh, road, driver)
            results = {
                "vehicle": f"{road_label} road · {driver_label} driver · {speed_kmh:,.0f} km/h",
                "primary_value": f"{stopping:,.2f}",
                "primary_unit": "m",
                "primary_label": "Total stopping distance",
                "rows": [
                    {"label": "Reaction distance", "value": f"{reaction:,.2f}", "unit": "m"},
                    {"label": "Braking distance", "value": f"{brake:,.2f}", "unit": "m"},
                    {"label": "Total stopping distance", "value": f"{stopping:,.2f}", "unit": "m"},
                ],
            }
        except (ValueError, KeyError) as exc:
            error = str(exc) or "Please check your inputs."

    return render_template(
        "braking.html",
        results=results,
        error=error,
        form=form,
        roads=roads,
        drivers=drivers,
        github=GITHUB_REPO,
        source=github_file("calculators/braking.py"),
    )


@app.route("/power-to-weight", methods=["GET", "POST"])
def power_to_weight_view():
    results = None
    error = None
    form = {"power": "", "weight": ""}

    if request.method == "POST":
        form = {
            "power": request.form.get("power", "").strip(),
            "weight": request.form.get("weight", "").strip(),
        }
        try:
            power_hp = float(form["power"])
            weight_kg = float(form["weight"])
            if power_hp <= 0 or weight_kg <= 0:
                raise ValueError("Power and weight must be greater than zero.")
            ratio, kg_per_hp = power_to_weight_ratio.calculate_power_to_weight(power_hp, weight_kg)
            results = {
                "vehicle": f"{power_hp:,.0f} hp · {weight_kg:,.0f} kg",
                "primary_value": f"{ratio:,.2f}",
                "primary_unit": "hp/tonne",
                "primary_label": "Power-to-Weight ratio",
                "rows": [
                    {"label": "Power-to-Weight ratio", "value": f"{ratio:,.2f}", "unit": "hp/tonne"},
                    {"label": "Weight per horsepower", "value": f"{kg_per_hp:,.2f}", "unit": "kg/hp"},
                ],
            }
        except ValueError as exc:
            error = str(exc) or "Please check your inputs."

    return render_template(
        "power_to_weight.html",
        results=results,
        error=error,
        form=form,
        github=GITHUB_REPO,
        source=github_file("calculators/power_to_weight_ratio.py"),
    )


@app.route("/rpm", methods=["GET", "POST"])
def rpm_view():
    results = None
    error = None
    form = {"speed": "", "tyre": "", "gear": "", "final_drive": ""}

    if request.method == "POST":
        form = {key: request.form.get(key, "").strip() for key in form}
        try:
            speed = float(form["speed"])
            tyre = float(form["tyre"])
            gear = float(form["gear"])
            final_drive = float(form["final_drive"])
            if min(speed, tyre, gear, final_drive) <= 0:
                raise ValueError("All values must be greater than zero.")
            wheel_rpm, engine_rpm = rpm_calculator.calculate_rpm(speed, tyre, gear, final_drive)
            results = {
                "vehicle": f'{tyre:,.1f}" tyres · gear {gear:,.2f} · final drive {final_drive:,.2f}',
                "primary_value": f"{engine_rpm:,.2f}",
                "primary_unit": "rpm",
                "primary_label": "Estimated engine RPM",
                "rows": [
                    {"label": "Wheel RPM", "value": f"{wheel_rpm:,.2f}", "unit": "rpm"},
                    {"label": "Estimated engine RPM", "value": f"{engine_rpm:,.2f}", "unit": "rpm"},
                ],
            }
        except ValueError as exc:
            error = str(exc) or "Please check your inputs."

    return render_template(
    "aero_drag.html",
    results=results,
    error=error,
    form=form,
    cars=get_all_cars(),
    github=GITHUB_REPO,
    source=github_file("calculators/aero_drag.py"),
)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
