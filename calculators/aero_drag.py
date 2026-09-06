# Aerodynamic Drag Calculator
# Calculates aerodynamic drag force and drag power of a vehicle.

import math
from database.mongo import cars_collection


AIR_DENSITY = 1.225  # kg/m³


def calculate_drag(speed_kmh, cd, area):
    """Return (drag_force_N, drag_power_hp, speed_ms)."""

    speed_ms = speed_kmh / 3.6

    drag_force = (0.5 * AIR_DENSITY * cd * area * (speed_ms ** 2))

    drag_power_hp = drag_force * speed_ms / 745.7

    return drag_force, drag_power_hp, speed_ms


def find_vehicle(name):
    """Find a vehicle in MongoDB and return its aerodynamic data."""

    vehicle = cars_collection.find_one(
        {
            "identity.name": {
                "$regex": f"^{name.strip()}$",
                "$options": "i"
            }
        },
        {
            "identity.name": 1,
            "aerodynamics": 1
        }
    )

    if vehicle:
        vehicle_name = vehicle["identity"]["name"]
        aerodynamics = vehicle.get("aerodynamics", {})

        cd = aerodynamics.get("cd")
        area = aerodynamics.get("frontal_area_m2")

        if cd is not None and area is not None:
            return vehicle_name, cd, area

    return None


if __name__ == "__main__":

    print("\n" + "=" * 55)
    print("              AERODYNAMIC DRAG CALCULATOR")
    print("=" * 55)

    vehicle = input("\nEnter vehicle name: ").strip()

    found = find_vehicle(vehicle)

    if found:
        name, cd, area = found

        print(f"\nVehicle: {name}")
        print(f"Drag Coefficient (Cd): {cd}")
        print(f"Frontal Area: {area} m²")

    else:
        print("\nVehicle not found or aerodynamic data unavailable.")
        print("Enter details manually.")

        cd = float(input("Enter drag coefficient: "))
        area = float(input("Enter frontal area (m²): "))

        name = vehicle

    speed_kmh = float(input("Enter Vehicle Speed (km/h): "))

    drag_force, drag_power_hp, _ = calculate_drag(speed_kmh,cd,area)

    print("\n" + "=" * 55)
    print("                       RESULTS")
    print("=" * 55)

    print(f"\nVehicle: {name}")
    print(f"Speed: {speed_kmh} km/h")
    print(f"Aerodynamic Drag Force: {drag_force:.2f} N")
    print(f"Drag Power: {drag_power_hp:.2f} hp")

    print("=" * 55)