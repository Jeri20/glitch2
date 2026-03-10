def allocate_slot(cancellation_event, waitlist):
    # Workflow: cancellation detected → retrieve waitlist → rank patients → select top candidates → send slot offer → first confirmation wins
    ranked = rank_patients(waitlist)
    top_candidates = ranked[:3]  # Example: top 3
    # TODO: send slot offer, await responses
    return top_candidates

from .ranking_model import rank_patients
