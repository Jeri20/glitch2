from fastapi import FastAPI
from app.routers import appointments, waitlist, admin, intake

app = FastAPI()

app.include_router(appointments.router)
app.include_router(waitlist.router)
app.include_router(admin.router)
app.include_router(intake.router)

@app.get("/")
def root():
    return {"message": "Intelligent Appointment Booking Agent API"}
