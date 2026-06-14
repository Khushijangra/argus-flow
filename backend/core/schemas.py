from pydantic import BaseModel
from typing import Optional

class SignalOverrideRequest(BaseModel):
    junction_id: str
    phase: str  # "NS_GREEN", "EW_GREEN", "YELLOW", "ALL_RED"
    duration: int = 60
    source: str = "operator"


class EmergencyActivateRequest(BaseModel):
    vehicle_id: str
    vehicle_type: str = "ambulance"
    origin: str  # Junction ID
    destination: str  # Junction ID


class JunctionSelectRequest(BaseModel):
    junction_id: str


class JunctionModeRequest(BaseModel):
    junction_id: str
    mode: str  # ai | manual | emergency
    lane: Optional[str] = None  # north|south|east|west
    duration: int = 60


class SecurityValidateRequest(BaseModel):
    junction_id: str
    new_phase: int
    source: str = "ai"


class SecuritySimulateRequest(BaseModel):
    attack_type: str  # replay, dos, mitm, conflicting
    junction_id: str = "J1_1"


class NLCommandRequest(BaseModel):
    text: str


class VoiceAnnounceRequest(BaseModel):
    message: str
    language: str = "en"
    play: bool = False  # Don't play audio on server by default


class CameraSourceModeRequest(BaseModel):
    mode: str  # live | upload


