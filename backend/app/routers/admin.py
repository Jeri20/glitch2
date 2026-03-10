from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/update-schedule")
def update_doctor_schedule():
    # TODO: Implement doctor schedule update
    return {"status": "doctor schedule updated"}

@router.post("/doctor-unavailable")
def doctor_unavailable():
    # TODO: Implement doctor unavailable workflow
    return {"status": "doctor unavailable"}
