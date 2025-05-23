import pandas as pd
import random
import pytz
from datetime import datetime, timedelta
from geopy.distance import geodesic
import plotly.express as px
import ast

riders_df = pd.read_csv("riders_df.csv")
stations_df = pd.read_csv("stations_df.csv")

riders_df["est_finish_ts"] = pd.to_datetime(riders_df["est_finish_ts"], errors='coerce')
import ast
from datetime import datetime

for i in range(1, 6):
    slot_key = f"slot_{i}"
    if slot_key in stations_df.columns:
        # Step 1: Convert stringified lists into actual Python lists
        stations_df[slot_key] = stations_df[slot_key].apply(
            lambda x: ast.literal_eval(x) if isinstance(x, str) else x
        )
        # Step 2: Convert all strings inside lists to datetime
        stations_df[slot_key] = stations_df[slot_key].apply(
            lambda lst: [datetime.fromisoformat(dt) if isinstance(dt, str) else dt for dt in lst] if lst else []
        )

def flag_riders_needing_swap(df, threshold=20, soc_min=10, avg_speed_kmph=25):
    projected_socs = []
    needs_swap_end = []
    needs_swap_midway = []
    swap_reasons = []

    for idx, row in df.iterrows():
        soc = row["soc_pct"]

        if row["status"] == "idle":
            projected_soc = soc
            end_needed = soc <= threshold
            projected_socs.append(projected_soc)
            needs_swap_end.append(end_needed)
            needs_swap_midway.append(False)

            swap_reason = "idle_low_soc" if end_needed else "idle_soc_ok"

        else:  # on_gig
            km_left = row["km_to_finish"]
            projected_soc = soc - (4 * km_left)

            # End-swap needed
            end_needed = projected_soc <= threshold

            # Midway check: if they dip below min (e.g., 10%) before delivery ends
            km_until_critical = (soc - soc_min) / 4
            midway_critical = km_until_critical < km_left

            needs_swap_end.append(end_needed)
            needs_swap_midway.append(midway_critical)
            projected_socs.append(projected_soc)

            if midway_critical:
                swap_reason = "midway_soc_critical"
            elif end_needed:
                swap_reason = "low_soc_at_end"
            else:
                swap_reason = "trip_possible_without_swap"

        swap_reasons.append(swap_reason)

    df["projected_soc"] = projected_socs
    df["needs_swap_end"] = needs_swap_end
    df["needs_swap_midway"] = needs_swap_midway
    df["needs_swap"] = df["needs_swap_end"] | df["needs_swap_midway"]
    df["swap_reason"] = swap_reasons

    return df

# Step 3: Apply the function
riders_df_need_swap = flag_riders_needing_swap(riders_df)

# --- CONFIGURATION ---
SWAP_TIME_MIN = 4
MAX_SLOTS = 5
SPEED_KMPH = 25
SOC_THRESHOLD = 20
NOW_UTC = datetime.strptime("2025-05-22T13:30:00Z", "%Y-%m-%dT%H:%M:%SZ")

# --- FILTER RIDERS THAT NEED SWAP ---
swap_riders = riders_df_need_swap[riders_df_need_swap["needs_swap"] == True].copy()
swap_riders["est_finish_ts"] = pd.to_datetime(swap_riders["est_finish_ts"], errors='coerce')

# --- PRIORITY RULES ---
def assign_priority(r):
    if r.get("needs_swap_midway", False):
        return 0
    elif r["status"] == "idle" and r["soc_pct"] < SOC_THRESHOLD:
        return 1
    elif r["status"] == "idle":
        return 2
    else:
        return 3

swap_riders["priority"] = swap_riders.apply(assign_priority, axis=1)
swap_riders = swap_riders.sort_values(by=["priority", "soc_pct", "est_finish_ts"], ascending=[True, True, True])

# --- SLOT FINDING FUNCTION ---
def find_best_slot(station_row, arrive_time):
    best_slot = None
    best_start_time = None
    min_start_time = datetime.max

    for i in range(1, MAX_SLOTS + 1):
        slot_key = f"slot_{i}"
        scheduled = station_row[slot_key]

        if scheduled:
            last_end = max(scheduled) + timedelta(minutes=SWAP_TIME_MIN)
            start_time = max(arrive_time, last_end)
        else:
            start_time = arrive_time

        if start_time < min_start_time:
            best_slot = slot_key
            best_start_time = start_time
            min_start_time = start_time

    return best_slot, best_start_time

# --- MAIN OPTIMIZER LOOP ---
plan_output = []
assigned_ids = set()

for idx, rider in swap_riders.iterrows():
    rider_loc = (rider["lat"], rider["lng"])
    soc = rider["soc_pct"]
    status = rider["status"]
    km_left = rider.get("km_to_finish", 0)
    max_travel_km = soc / 4
    best_plan = None
    min_total_minutes = float("inf")

    # --- Determine available time ---
    if rider.get("needs_swap_midway", False):
        available_time = NOW_UTC
    elif status == "idle":
        available_time = NOW_UTC
    elif rider.get("needs_swap_end", False):
        available_time = rider["est_finish_ts"]
    else:
        continue  # No swap needed

    # --- Sort stations by distance ---
    station_distances = []
    for s_idx, station in stations_df.iterrows():
        distance_km = geodesic(rider_loc, (station["lat"], station["lng"])).km
        station_distances.append((s_idx, distance_km))
    station_distances.sort(key=lambda x: x[1])  # Closest first

    for s_idx, distance_km in station_distances:
        if distance_km > max_travel_km:
            continue

        station = stations_df.loc[s_idx]
        travel_time_min = distance_km / SPEED_KMPH * 60
        arrive_time = available_time + timedelta(minutes=travel_time_min)

        best_slot, swap_start_time = find_best_slot(station, arrive_time)
        if swap_start_time is None:
            continue

        swap_end_time = swap_start_time + timedelta(minutes=SWAP_TIME_MIN)
        total_time_min = (swap_end_time - NOW_UTC).total_seconds() / 60

        if (swap_end_time - NOW_UTC).total_seconds() <= 3600 and total_time_min < min_total_minutes:
            best_plan = {
                "rider_id": rider["rider_id"],
                "station_id": station["station_id"],
                "slot_used": best_slot,
                "depart_ts": available_time.isoformat() + "Z",
                "arrive_ts": arrive_time.isoformat() + "Z",
                "swap_start_ts": swap_start_time.isoformat() + "Z",
                "swap_end_ts": swap_end_time.isoformat() + "Z",
                "eta_back_lat": station["lat"] if status == "on_gig" and distance_km < km_left else rider["lat"],
                "eta_back_lng": station["lng"] if status == "on_gig" and distance_km < km_left else rider["lng"]
            }
            best_station_idx = s_idx
            best_slot_key = best_slot
            min_total_minutes = total_time_min
            break

    if best_plan:
        plan_output.append(best_plan)
        assigned_ids.add(best_plan["rider_id"])
        stations_df.at[best_station_idx, best_slot_key].append(
            datetime.fromisoformat(best_plan["swap_start_ts"].replace("Z", ""))
        )

# --- UPDATE riders_df_need_swap ---
riders_df_need_swap["assigned"] = riders_df_need_swap["rider_id"].isin(assigned_ids)
riders_df_need_swap["max_travel_km"] = riders_df_need_swap["soc_pct"] / 4

station_coords = stations_df[["station_id", "lat", "lng"]].to_dict(orient="records")

def determine_reason(row):
    if row["assigned"] or not row["needs_swap"]:
        return None
    rider_loc = (row["lat"], row["lng"])
    max_km = row["max_travel_km"]
    for station in sorted(station_coords, key=lambda s: geodesic(rider_loc, (s["lat"], s["lng"])).km):
        distance = geodesic(rider_loc, (station["lat"], station["lng"])).km
        if distance <= max_km:
            return "No available slots within 60 minutes"
    return "Cannot reach any station with current SOC"

riders_df_need_swap["reason_for_no_swap"] = riders_df_need_swap.apply(determine_reason, axis=1)

# --- EXPORT ---
plan_output_df = pd.DataFrame(plan_output)
plan_output_df.to_csv("plan_output_slot_based.csv", index=False)
riders_df_need_swap.to_csv("riders_df_with_status.csv", index=False)
