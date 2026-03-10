def rank_patients(waitlist):
    # score = (wait_hours × 0.5) + (urgency × 30) - min(distance_km × 1.2, 15)
    ranked = sorted(waitlist, key=lambda entry: (entry.wait_hours * 0.5) + (entry.urgency * 30) - min(entry.distance_km * 1.2, 15), reverse=True)
    return ranked
