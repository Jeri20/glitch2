def predict_eta(distance_km, time_until_slot):
    travel_time_minutes = distance_km * 3
    return travel_time_minutes <= time_until_slot
