"""Input validation for the quote wizard.

Every parser returns a normalized value or raises ValidationError with a
message that can be shown to the customer as-is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from email_validator import EmailNotValidError, validate_email


class ValidationError(ValueError):
    """Raised with a customer-facing explanation."""


US_STATES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
}
_STATE_BY_NAME = {name.upper(): code for code, name in US_STATES.items()}

MAX_NAME = 100
MAX_COMPANY = 150
MAX_DETAILS = 1000
MAX_WEIGHT_LB = 500_000
MAX_DAYS_AHEAD = 365

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(value: str) -> str:
    """Strip control characters and collapse whitespace on a single line."""
    return re.sub(r"\s+", " ", _CONTROL_CHARS.sub("", value)).strip()


def parse_full_name(value: str) -> str:
    name = clean_text(value)
    if len(name) < 2:
        raise ValidationError("Please enter your full name (at least 2 characters).")
    if len(name) > MAX_NAME:
        raise ValidationError(f"Please keep your name under {MAX_NAME} characters.")
    if not re.search(r"[^\W\d_]", name):
        raise ValidationError("Please enter a name using letters.")
    if name.startswith("/"):
        raise ValidationError("Please enter your full name, not a command.")
    return name


def parse_company(value: str) -> str:
    company = clean_text(value)
    if len(company) < 2:
        raise ValidationError("Please enter your company name, or tap “Individual / Not applicable”.")
    if len(company) > MAX_COMPANY:
        raise ValidationError(f"Please keep the company name under {MAX_COMPANY} characters.")
    return company


def parse_email(value: str) -> str:
    raw = value.strip()
    if len(raw) > 254:
        raise ValidationError("That email address is too long.")
    try:
        result = validate_email(raw, check_deliverability=False)
    except EmailNotValidError:
        raise ValidationError("That doesn't look like a valid email address. Example: name@company.com") from None
    return result.normalized


def parse_phone(value: str) -> str:
    """Normalize to E.164 (+<country><number>).

    International numbers must include the country code. A bare 10-digit number
    is treated as US/Canada (+1) for convenience.
    """
    raw = value.strip()
    if not re.fullmatch(r"[+\d\s().\-]{7,25}", raw):
        raise ValidationError("Please enter a phone number with country code, e.g. +1 215 555 0123.")
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        normalized = "+" + digits
    elif raw.startswith("00"):
        normalized = "+" + digits[2:]
    elif len(digits) == 10:
        normalized = "+1" + digits
    elif len(digits) == 11 and digits.startswith("1"):
        normalized = "+" + digits
    else:
        raise ValidationError("Please include your country code, starting with +. Example: +1 215 555 0123.")
    if not 8 <= len(normalized) - 1 <= 15 or normalized[1] == "0":
        raise ValidationError("That phone number doesn't look complete. Please include the country code.")
    if normalized.startswith("+1") and len(normalized) != 12:
        raise ValidationError("US and Canadian numbers have 10 digits after +1. Please check the number.")
    return normalized


@dataclass(frozen=True)
class Location:
    city: str
    state: str
    zip_code: str | None

    def display(self) -> str:
        return f"{self.city}, {self.state}" + (f" {self.zip_code}" if self.zip_code else "")


_LOCATION = re.compile(
    r"^(?P<city>[^,]{2,80}),\s*(?P<state>[A-Za-z][A-Za-z .]{1,24}?)\.?(?:\s*,?\s*(?P<zip>\d{5}(?:-\d{4})?))?$"
)


def parse_location(value: str) -> Location:
    text = clean_text(value)
    match = _LOCATION.match(text)
    if not match:
        raise ValidationError(
            "Please send the city and state, with the ZIP code if you have it.\nExample: Dallas, TX 75201"
        )
    city = match.group("city").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,79}", city):
        raise ValidationError("Please check the city name. Example: Dallas, TX 75201")
    state_raw = match.group("state").strip().upper()
    state = state_raw if state_raw in US_STATES else _STATE_BY_NAME.get(state_raw)
    if not state:
        raise ValidationError("Please use a US state, e.g. TX or Texas. Example: Dallas, TX 75201")
    return Location(
        city=city.title() if city.islower() or city.isupper() else city, state=state, zip_code=match.group("zip")
    )


_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y")


def parse_pickup_date(value: str, today: date) -> date:
    text = clean_text(value).lower()
    if text == "today":
        parsed = today
    elif text == "tomorrow":
        parsed = today + timedelta(days=1)
    else:
        parsed = None
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(text.title() if "%b" in fmt or "%B" in fmt else text, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValidationError("Please send the date as MM/DD/YYYY, for example 11/04/2026.")
    if parsed < today:
        raise ValidationError("That date is in the past. Please choose today or a later date.")
    if parsed > today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError("Please choose a pickup date within the next 12 months.")
    return parsed


def parse_weight(value: str) -> int:
    text = clean_text(value).lower().replace(",", "")
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)?\.?", text)
    if not match:
        raise ValidationError("Please send the approximate weight in pounds as a number, e.g. 42000.")
    weight = float(match.group(1))
    if weight <= 0:
        raise ValidationError("The weight must be greater than zero.")
    if weight > MAX_WEIGHT_LB:
        raise ValidationError(f"That weight looks too high. Please send it in pounds (max {MAX_WEIGHT_LB:,} lb).")
    return max(1, round(weight))


def parse_details(value: str) -> str:
    text = _CONTROL_CHARS.sub("", value).strip()
    if len(text) > MAX_DETAILS:
        raise ValidationError(f"Please keep shipment details under {MAX_DETAILS} characters (you sent {len(text)}).")
    if not text:
        raise ValidationError("Please describe the shipment, or tap “Skip”.")
    return text
