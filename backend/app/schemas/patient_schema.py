from pydantic import BaseModel

class PatientSchema(BaseModel):
    id: int
    name: str
    phone: str
    location: str = None
    latitude: float = None
    longitude: float = None

    class Config:
        orm_mode = True
