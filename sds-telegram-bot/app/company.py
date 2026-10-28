"""Company content (contact details, services, freight types) loaded from config/company.toml.

Nothing here should be invented: every value comes from the TOML file that SDS maintains.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


class ContactInfo(BaseModel):
    phone: str | None = None
    email: EmailStr | None = None
    website: HttpUrl | None = None
    office_hours: str | None = None
    office_address: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class Service(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,24}$")
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=400)
    # Only services confirmed by SDS management should be enabled.
    enabled: bool = False


class FreightType(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,24}$")
    label: str = Field(min_length=1, max_length=40)
    enabled: bool = True


class CompanyConfig(BaseModel):
    name: str = "SDS"
    bot_name: str = "SDS Trucking"
    slogan: str = "Moving America Forward."
    about: str
    contact: ContactInfo = ContactInfo()
    services: list[Service] = []
    freight_types: list[FreightType] = []

    @field_validator("services", "freight_types")
    @classmethod
    def _unique_keys(cls, items: list) -> list:
        keys = [i.key for i in items]
        if len(keys) != len(set(keys)):
            raise ValueError("keys must be unique")
        return items

    @property
    def enabled_services(self) -> list[Service]:
        return [s for s in self.services if s.enabled]

    @property
    def enabled_freight_types(self) -> list[FreightType]:
        return [f for f in self.freight_types if f.enabled]

    def service(self, key: str) -> Service | None:
        return next((s for s in self.services if s.key == key), None)

    def freight_type(self, key: str) -> FreightType | None:
        return next((f for f in self.enabled_freight_types if f.key == key), None)


def load_company_config(path: Path) -> CompanyConfig:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return CompanyConfig.model_validate(data)
