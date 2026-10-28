from datetime import date

import pytest

from app.utils.validation import (
    ValidationError,
    parse_company,
    parse_details,
    parse_email,
    parse_full_name,
    parse_location,
    parse_phone,
    parse_pickup_date,
    parse_weight,
)

TODAY = date(2026, 10, 28)


class TestEmail:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("jane@acme.com", "jane@acme.com"),
            ("  Jane.Doe+freight@Acme-Logistics.COM ", "Jane.Doe+freight@acme-logistics.com"),
            ("ops@sub.domain.co", "ops@sub.domain.co"),
        ],
    )
    def test_valid(self, raw, expected):
        assert parse_email(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["", "jane", "jane@", "@acme.com", "jane@acme", "jane @acme.com", "a" * 250 + "@x.com"]
    )
    def test_invalid(self, raw):
        with pytest.raises(ValidationError):
            parse_email(raw)


class TestPhone:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("+1 (215) 268-3886", "+12152683886"),
            ("215-268-3886", "+12152683886"),  # bare 10 digits → US/Canada
            ("1 215 268 3886", "+12152683886"),
            ("+44 20 7946 0958", "+442079460958"),  # international numbers are accepted
            ("+998 90 123 45 67", "+998901234567"),
            ("0049 30 1234567", "+49301234567"),
        ],
    )
    def test_valid(self, raw, expected):
        assert parse_phone(raw) == expected

    @pytest.mark.parametrize("raw", ["", "12345", "phone please", "+1 215 268 388", "+0 123 456 7890", "2152683886x12"])
    def test_invalid(self, raw):
        with pytest.raises(ValidationError):
            parse_phone(raw)


class TestLocation:
    @pytest.mark.parametrize(
        ("raw", "city", "state", "zip_code"),
        [
            ("Dallas, TX 75201", "Dallas", "TX", "75201"),
            ("dallas, tx", "Dallas", "TX", None),
            ("Atlanta, Georgia", "Atlanta", "GA", None),
            ("New York, New York 10001-1234", "New York", "NY", "10001-1234"),
            ("St. Louis, MO, 63101", "St. Louis", "MO", "63101"),
        ],
    )
    def test_valid(self, raw, city, state, zip_code):
        loc = parse_location(raw)
        assert (loc.city, loc.state, loc.zip_code) == (city, state, zip_code)

    @pytest.mark.parametrize(
        "raw", ["Dallas", "Dallas TX", "Dallas, Ontario", "Dallas, ZZ", "123, TX", "Dallas, TX 123"]
    )
    def test_invalid(self, raw):
        with pytest.raises(ValidationError):
            parse_location(raw)


class TestPickupDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("11/04/2026", date(2026, 11, 4)),
            ("2026-11-04", date(2026, 11, 4)),
            ("11-04-2026", date(2026, 11, 4)),
            ("Nov 4, 2026", date(2026, 11, 4)),
            ("today", TODAY),
            ("Tomorrow", date(2026, 10, 29)),
            ("10/28/2026", TODAY),
        ],
    )
    def test_valid(self, raw, expected):
        assert parse_pickup_date(raw, TODAY) == expected

    def test_past_date_rejected(self):
        with pytest.raises(ValidationError, match="past"):
            parse_pickup_date("10/27/2026", TODAY)

    def test_too_far_ahead_rejected(self):
        with pytest.raises(ValidationError, match="12 months"):
            parse_pickup_date("12/01/2027", TODAY)

    @pytest.mark.parametrize("raw", ["next week", "13/45/2026", "2026/11/04x", ""])
    def test_unparseable(self, raw):
        with pytest.raises(ValidationError):
            parse_pickup_date(raw, TODAY)


class TestWeight:
    @pytest.mark.parametrize(
        ("raw", "expected"), [("42000", 42000), ("42,000 lb", 42000), ("1500 lbs", 1500), ("750.4 pounds", 750)]
    )
    def test_valid(self, raw, expected):
        assert parse_weight(raw) == expected

    @pytest.mark.parametrize("raw", ["0", "-5", "-1500 lb", "0.0", "heavy", "42 tons", "600000"])
    def test_invalid(self, raw):
        with pytest.raises(ValidationError):
            parse_weight(raw)


class TestTextFields:
    def test_name(self):
        assert parse_full_name("  Jane   Carter ") == "Jane Carter"
        for bad in ["J", "12345", "/start", "x" * 101]:
            with pytest.raises(ValidationError):
                parse_full_name(bad)

    def test_company(self):
        assert parse_company("Acme  Logistics LLC") == "Acme Logistics LLC"
        with pytest.raises(ValidationError):
            parse_company("A")

    def test_details_limit(self):
        assert parse_details("  22 pallets\nno liftgate ") == "22 pallets\nno liftgate"
        with pytest.raises(ValidationError, match="1000"):
            parse_details("x" * 1001)
