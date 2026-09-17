from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database import Base


class SectionModel(Base):
    """Track Topology Section model representing high-density railway corridors."""

    __tablename__ = "sections"

    section_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    line_type = Column(String(20), nullable=False)
    start_station = Column(String(20), nullable=False)
    end_station = Column(String(20), nullable=False)
    start_km = Column(Float, nullable=False)
    end_km = Column(Float, nullable=False)
    max_speed_kmh = Column(Integer, nullable=False)
    traffic_density_index = Column(Float, nullable=False)

    requests = relationship(
        "MaintenanceRequestModel",
        back_populates="section",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "section_id": self.section_id,
            "name": self.name,
            "line_type": self.line_type,
            "start_station": self.start_station,
            "end_station": self.end_station,
            "start_km": self.start_km,
            "end_km": self.end_km,
            "max_speed_kmh": self.max_speed_kmh,
            "traffic_density_index": self.traffic_density_index,
        }


class MaintenanceRequestModel(Base):
    """
    Unified maintenance block request model representing departmental possession
    requests from Engineering (P-Way/TMS), S&T (SMMS), TRD (TDMS), and Operations (COA).
    """

    __tablename__ = "maintenance_requests"

    request_id = Column(String(50), primary_key=True, index=True)
    source_system = Column(String(20), nullable=False, index=True)
    department = Column(String(20), nullable=False, index=True)
    section_id = Column(String(50), ForeignKey("sections.section_id"), nullable=False, index=True)
    corridor_slot = Column(String(50), nullable=False)
    chainage_start = Column(Float, nullable=False)
    chainage_end = Column(Float, nullable=False)
    requested_window_start = Column(DateTime, nullable=False, index=True)
    requested_window_end = Column(DateTime, nullable=False)
    required_duration_minutes = Column(Integer, nullable=False)
    work_type = Column(String(150), nullable=False)
    asset_id = Column(String(100), nullable=False, index=True)
    asset_type = Column(String(100), nullable=False)
    asset_age_years = Column(Float, nullable=False)
    last_maintenance_days_ago = Column(Integer, nullable=False)
    past_breakdown_count = Column(Integer, nullable=False)
    gross_million_tonnes = Column(Float, nullable=False)
    condition_score = Column(Float, nullable=False)
    urgency_category = Column(String(20), nullable=False, index=True)
    asset_age_or_condition_features = Column(JSON, nullable=True)
    asset_condition_features = Column(JSON, nullable=True)
    risk_score = Column(Float, nullable=True, default=None)
    requires_power_block = Column(Boolean, nullable=False, default=False)
    requires_traffic_block = Column(Boolean, nullable=False, default=False)
    status = Column(String(30), nullable=False, default="PENDING", index=True)

    section = relationship("SectionModel", back_populates="requests")

    def to_dict(self):
        features = self.asset_age_or_condition_features or {
            "asset_age_years": self.asset_age_years,
            "last_maintenance_days_ago": self.last_maintenance_days_ago,
            "past_breakdown_count": self.past_breakdown_count,
            "gross_million_tonnes": self.gross_million_tonnes,
            "condition_score": self.condition_score,
            "urgency_category": self.urgency_category,
        }
        if self.risk_score is not None:
            score_val = round(self.risk_score, 2)
        else:
            try:
                from app.risk_model import predict_risk_score
                score_val = predict_risk_score(features)
            except Exception:
                score_val = 0.0
        return {
            "request_id": self.request_id,
            "source_system": self.source_system,
            "department": self.department,
            "section_id": self.section_id,
            "corridor_slot": self.corridor_slot,
            "chainage_start": self.chainage_start,
            "chainage_end": self.chainage_end,
            "requested_window_start": self.requested_window_start.isoformat() if self.requested_window_start else None,
            "requested_window_end": self.requested_window_end.isoformat() if self.requested_window_end else None,
            "required_duration_minutes": self.required_duration_minutes,
            "work_type": self.work_type,
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "asset_age_years": self.asset_age_years,
            "last_maintenance_days_ago": self.last_maintenance_days_ago,
            "past_breakdown_count": self.past_breakdown_count,
            "gross_million_tonnes": self.gross_million_tonnes,
            "condition_score": self.condition_score,
            "urgency_category": self.urgency_category,
            "asset_age_or_condition_features": features,
            "asset_condition_features": features,
            "risk_score": score_val,
            "requires_power_block": self.requires_power_block,
            "requires_traffic_block": self.requires_traffic_block,
            "status": self.status,
        }
