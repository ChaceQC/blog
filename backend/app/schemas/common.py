from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    checks: dict[str, str]

    model_config = ConfigDict(extra="forbid")
