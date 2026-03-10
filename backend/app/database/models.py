from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Time, Boolean
from sqlalchemy.orm import relationship
from app.database.db import Base

class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    location = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    appointments = relationship('Appointment', back_populates='patient')
    waitlist_entries = relationship('WaitlistEntry', back_populates='patient')

class Doctor(Base):
    __tablename__ = 'doctors'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialty = Column(String)
    appointments = relationship('Appointment', back_populates='doctor')

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey('doctors.id'))
    patient_id = Column(Integer, ForeignKey('patients.id'))
    date = Column(Date)
    time = Column(Time)
    status = Column(String)
    locked = Column(Boolean, default=False)
    doctor = relationship('Doctor', back_populates='appointments')
    patient = relationship('Patient', back_populates='appointments')

class WaitlistEntry(Base):
    __tablename__ = 'waitlist'
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey('patients.id'))
    urgency = Column(Integer)
    wait_hours = Column(Integer)
    distance_km = Column(Float)
    status = Column(String)
    patient = relationship('Patient', back_populates='waitlist_entries')

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey('patients.id'))
    content = Column(String)
    status = Column(String)

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey('appointments.id'))
    content = Column(String)
    status = Column(String)
