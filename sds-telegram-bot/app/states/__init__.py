from aiogram.fsm.state import State, StatesGroup


class QuoteForm(StatesGroup):
    full_name = State()
    company = State()
    email = State()
    phone = State()
    pickup = State()
    delivery = State()
    pickup_date = State()
    freight_type = State()
    weight = State()
    details = State()
    review = State()


# Order of the wizard; used for Back navigation and edit mode.
QUOTE_STEPS: list[str] = [
    "full_name",
    "company",
    "email",
    "phone",
    "pickup",
    "delivery",
    "pickup_date",
    "freight_type",
    "weight",
    "details",
]


class TrackingForm(StatesGroup):
    reference = State()


class AdminInput(StatesGroup):
    note = State()
    message = State()
