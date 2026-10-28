import re
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def valid_email(value: str):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Gunakan alamat email yang valid")
    return value


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        return valid_email(value)


class CheckIn(StrictModel):
    request_id: UUID


class Version(StrictModel):
    expected_version: StrictInt = Field(ge=1)


class ProposeCorrection(Version):
    proposed_start: AwareDatetime
    proposed_end: AwareDatetime
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def interval(self):
        seconds = (self.proposed_end - self.proposed_start).total_seconds()
        if seconds <= 0 or seconds > 86400:
            raise ValueError("Durasi koreksi harus lebih dari 0 dan paling lama 24 jam")
        return self


class Decision(Version):
    note: str = Field(default="", max_length=2000)
