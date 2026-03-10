from pydantic import BaseModel
from datetime import date, time

class AppointmentSchema(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    date: date
    time: time
    status: str
    locked: bool

    class Config:
        orm_mode = True
