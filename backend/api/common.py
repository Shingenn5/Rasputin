from fastapi import Request
from pydantic import BaseModel, ConfigDict

def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])

class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

def current_user(request: Request):
    return {"username": "admin", "role": "admin"}

from backend.engine.agent import AgentHub
hub = AgentHub()

