from sqlalchemy import Column, Integer, Float, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True, index=True)
    date_label = Column(String(50))
    time_period = Column(String(20))
    upload_time = Column(DateTime, default=datetime.now)
    original_csv = Column(String(255))
    original_xlsx = Column(String(255))
    device_name = Column(String(100))
    device_model = Column(String(100))
    serial_number = Column(String(50))
    location = Column(String(255))
    notes = Column(Text)
    climate_records = relationship("ClimateRecord", back_populates="batch", cascade="all, delete-orphan")
    behavior_records = relationship("BehaviorRecord", back_populates="batch", cascade="all, delete-orphan")

class ClimateRecord(Base):
    __tablename__ = "climate_records"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), index=True)
    timestamp = Column(DateTime, index=True)
    temperature = Column(Float)
    wet_bulb_temp = Column(Float)
    globe_temperature = Column(Float)
    relative_humidity = Column(Float)
    barometric_pressure = Column(Float)
    altitude = Column(Float)
    station_pressure = Column(Float)
    wind_speed = Column(Float)
    heat_index = Column(Float)
    dew_point = Column(Float)
    density_altitude = Column(Float)
    crosswind = Column(Float)
    headwind = Column(Float)
    compass_magnetic = Column(Float)
    nwb_temp = Column(Float)
    compass_true = Column(Float)
    thermal_work_limit = Column(Float)
    wbgt = Column(Float)
    wind_chill = Column(Float)
    batch = relationship("Batch", back_populates="climate_records")

class BehaviorRecord(Base):
    __tablename__ = "behavior_records"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    gender = Column(String(10))
    age = Column(String(30))
    clothing_color = Column(String(20))
    clothing_thickness = Column(String(10))
    clothing_coverage = Column(String(10))
    chair_environment = Column(String(30))
    chair_number = Column(Integer)
    behavior_category = Column(String(20))
    behavior_detail = Column(String(100))
    weather_change_from = Column(String(50))
    weather_change_to = Column(String(50))
    weather_change_time = Column(String(30))
    active_adjustments = Column(String(200))
    orientation = Column(String(20))
    num_people = Column(String(30))
    batch = relationship("Batch", back_populates="behavior_records")
