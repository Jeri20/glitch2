from fastapi import APIRouter

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

@router.get("")
def get_ranked_waitlist():
    # TODO: Implement waitlist ranking
    return {"status": "waitlist ranked"}

@router.post("/add")
def add_patient_to_waitlist():
    # TODO: Implement add to waitlist
    return {"status": "patient added to waitlist"}
