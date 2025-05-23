import pandas as pd
import random
import pytz
from datetime import datetime, timedelta

# Generating the dataset
random.seed(104)

# Step 1: Generate 'rider_id' column for 100 riders
# Rider IDs from R001 to R100
rider_ids = [f"R{str(i).zfill(3)}" for i in range(1, 101)]

# Create a DataFrame
riders_df = pd.DataFrame({"rider_id": rider_ids})

# Step 2: Generate 'lat' and 'lng' near Pune
BASE_LAT = 18.5204
BASE_LNG = 73.8567
DELTA = 0.01  # ~1 km variation in all directions

# Generate coordinates
riders_df["lat"] = [BASE_LAT + random.uniform(-DELTA, DELTA) for _ in range(len(riders_df))]
riders_df["lng"] = [BASE_LNG + random.uniform(-DELTA, DELTA) for _ in range(len(riders_df))]

# Step 3: Generate 'soc_pct' (battery percentage)

# Random integer between 10% and 100%
riders_df["soc_pct"] = [random.randint(10, 100) for _ in range(len(riders_df))]

# Step 4: Assign 'status' based on 7 PM peak time for a Blinkit-like company
# 70% chance of being 'on_gig', 30% chance of being 'idle'

riders_df["status"] = [random.choices(["on_gig", "idle"], weights=[0.7, 0.3])[0] for _ in range(len(riders_df))]

# Step 5: Add 'km_to_finish' and 'est_finish_ts' for on_gig riders

# Define IST timezone using pytz
ist = pytz.timezone("Asia/Kolkata")

# Step 1: Define 7:00 PM IST on May 22, 2025
ist_time = ist.localize(datetime(2025, 5, 22, 19, 0, 0))

# Step 2: Convert IST time to UTC
now_utc = ist_time.astimezone(pytz.UTC)

km_to_finish_list = []
est_finish_ts_list = []

for status in riders_df["status"]:
    if status == "on_gig":
        km = round(random.uniform(1.0, 6.0), 2)
        finish_time = now_utc + timedelta(minutes=int(km * 3))  # 20 km/h → 3 min per km
        km_to_finish_list.append(km)
        est_finish_ts_list.append(finish_time.isoformat() + "Z")
    else:
        km_to_finish_list.append(None)
        est_finish_ts_list.append(None)

riders_df["km_to_finish"] = km_to_finish_list
riders_df["est_finish_ts"] = est_finish_ts_list

random.seed(100)
# Constants
BASE_LAT = 18.5204
BASE_LNG = 73.8567
STATION_DELTA = 0.01
station_ids = ["S_A", "S_B", "S_C"]
SWAP_TIME_MIN = 4
NOW_UTC = datetime.strptime("2025-05-22T13:30:00Z", "%Y-%m-%dT%H:%M:%SZ")

def next_available_slot(slots):
    """
    Return the index of the slot (0-4) that will be free the earliest.
    """
    end_times = [
        max(times) + timedelta(minutes=SWAP_TIME_MIN) if times else random.choices([NOW_UTC,NOW_UTC+timedelta(minutes=1),NOW_UTC+timedelta(minutes=2)],[0.3,0.3,0.3])[0]
        for times in slots
    ]
    return end_times.index(min(end_times)), min(end_times)

# Generate station data
station_data = []

for station_id in station_ids:
    lat = BASE_LAT + random.uniform(-STATION_DELTA, STATION_DELTA)
    lng = BASE_LNG + random.uniform(-STATION_DELTA, STATION_DELTA)
    queue_len = random.randint(0, 10)

    # Initialize 5 empty slots (each slot is a list of swap start times)
    slots = [[] for _ in range(5)]

    for _ in range(queue_len):
        slot_idx, available_at = next_available_slot(slots)
        slots[slot_idx].append(available_at)

    # Flatten into dictionary with slot_1, ..., slot_5
    station_row = {
        "station_id": station_id,
        "lat": lat,
        "lng": lng,
    }
    for i in range(5):
        station_row[f"slot_{i+1}"] = slots[i]

    station_data.append(station_row)

stations_df = pd.DataFrame(station_data)

# Exporting the simulated data for usage
for i in range(1, 6):
    slot_key = f"slot_{i}"
    stations_df[slot_key] = stations_df[slot_key].apply(
        lambda lst: [dt.isoformat() for dt in lst]
    )

stations_df.to_csv("stations_df.csv", index=False)
riders_df.to_csv('riders_df.csv', index=False)
