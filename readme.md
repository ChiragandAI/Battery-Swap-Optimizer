# 🔋 Battery Swap Routing Optimizer – Final Solution

## 🎯 Objective

Design an optimizer that schedules battery swaps for 100 riders in the next 60 minutes such that:

- No rider’s SOC drops below 10% before a swap  
- Total detour distance to stations is minimized  
- Station queues (5-slot parallel swap bays) never exceed capacity  
- Each swap takes 4 minutes and restores SOC to 100%  

---

## 🧠 Assumptions

| Parameter         | Value             |
|------------------|-------------------|
| Riders           | 100               |
| Stations         | 3                 |
| SOC drain rate   | 4% per km         |
| Speed            | 25 km/h (avg)     |
| Max swap slots   | 5 per station     |
| Swap time        | 4 minutes         |
| Schedule window  | 60 minutes        |

---

## 🧪 Dataset Simulation

### Riders
- Simulated around Pune
- Statuses include `on_gig` and `idle`
- Key fields: `rider_id`, `lat`, `lng`, `soc_pct`, `status`, `km_to_finish`, `est_finish_ts`

### Stations
- 3 stations with 5 parallel slots each (`slot_1` to `slot_5`)
- Queues simulated using future `datetime` objects

---

## ⚙️ Algorithm & Heuristics

### 1. Swap Need Classification
Riders are flagged with:
- `needs_swap_midway`: SOC drops below 10% during delivery  
- `needs_swap_end`: SOC drops below 20% by end of delivery  
- `needs_swap`: either of the above  
- `swap_reason`: e.g., `midway_soc_critical`, `low_soc_at_end`

### 2. Priority Sorting
Riders are prioritized as follows:
1. Midway-critical
2. Idle with low SOC
3. Idle with OK SOC
4. On-gig, swap needed after delivery

Sorted by priority → SOC → `est_finish_ts`.

### 3. Slot-Based Assignment
- Each station has 5 independent queues
- Riders are assigned to the **earliest available slot** they can reach
- Post-delivery swaps are scheduled if they still fit within the 60-minute window

### 4. Reason Logging
Unassigned riders are given:
- `"No available slots within 60 minutes"` or  
- `"Cannot reach any station with current SOC"`

---

## 🧱 Implementation Summary (`main.py`)

### 1. Data Import & Cleanup
- Parsed `est_finish_ts` in `riders_df`
- Converted `slot_1` to `slot_5` in `stations_df` from stringified lists → real datetime lists

### 2. Flagging Swap Need
- Used a `flag_riders_needing_swap()` function
- Labeled riders based on SOC projections
- Marked `needs_swap`, `needs_swap_midway`, `needs_swap_end`, and `swap_reason`

### 3. Priority Assignment
- Riders ranked by urgency using `assign_priority()`
- Ensured critical riders are always handled first

### 4. Slot Scheduling
- `find_best_slot()` picks the best slot and time across all 5 bays
- Ensures the slot is **available** and **swap ends within 60 mins**

### 5. Optimization Loop
- Riders are assigned to the nearest reachable station
- Swap times, slots, and returns are logged
- Riders only assigned if all constraints are satisfied

### 6. Assignment Summary
- `assigned` flag updated
- `reason_for_no_swap` filled if swap isn’t possible
- Final schedule stored in `plan_output`

---

## 📈 Scalability Thoughts (Short)

- **Batch scheduling** (e.g., every 5 mins) can reduce computational load  
- **Spatial indexing** (e.g., KD-Trees) can accelerate nearest-station lookup  
- **Parallel processing** will scale optimization to 1000s of riders  
- **Heuristic or OR-based** methods can improve global efficiency  
- **Real-time APIs and maps** can provide better ETA-based routing

---

## 📦 Deliverables

- `main.py` – core script running the full optimizer  
- `riders_df_with_status.csv` – rider-level flags, priorities, and reasoning  
- `plan_output_slot_based.csv` – scheduled swap plans including slot and time  
- `Battery_Swap_Optimizer.ipynb` – notebook version with stepwise logic and visuals  

---

**Author**: Chirag Dahiya  
**Date**: May 22, 2025  
