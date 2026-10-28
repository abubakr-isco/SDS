"""Offline Telegram harness: feeds fake updates into the dispatcher and records outgoing API calls."""

from __future__ import annotations

import itertools
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters.callback_data import CallbackData
from aiogram.methods import AnswerCallbackQuery, EditMessageText, GetMe, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update, User

BOT_TOKEN = "123456789:" + "A" * 35


class MockedSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self.blocked_chats: set[int] = set()
        self._ids = itertools.count(1000)

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        self.requests.append(method)
        chat_id = getattr(method, "chat_id", None)
        if isinstance(method, SendMessage) and chat_id in self.blocked_chats:
            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
        if isinstance(method, SendMessage):
            return Message(
                message_id=next(self._ids),
                date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, GetMe):
            return User(id=bot.id, is_bot=True, first_name="SDS Trucking", username="SDS_TruckBot")
        return True

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        yield b""

    async def close(self) -> None:
        pass


class MockedBot(Bot):
    def __init__(self) -> None:
        super().__init__(BOT_TOKEN, session=MockedSession(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    @property
    def mock(self) -> MockedSession:
        return self.session  # type: ignore[return-value]


class Harness:
    """Drive the dispatcher like a Telegram user would."""

    def __init__(self, dp: Dispatcher, bot: MockedBot) -> None:
        self.dp = dp
        self.bot = bot
        self._update_ids = itertools.count(1)
        self._message_ids = itertools.count(1)

    @staticmethod
    def user(user_id: int) -> User:
        return User(id=user_id, is_bot=False, first_name=f"User{user_id}")

    def _message(self, user_id: int, chat_type: str = "private", **fields: Any) -> Message:
        return Message(
            message_id=next(self._message_ids),
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type=chat_type),
            from_user=self.user(user_id),
            **fields,
        )

    async def _feed(self, update: Update) -> list[TelegramMethod]:
        start = len(self.bot.mock.requests)
        await self.dp.feed_update(self.bot, update)
        return self.bot.mock.requests[start:]

    async def send(self, user_id: int, text: str, chat_type: str = "private") -> list[TelegramMethod]:
        message = self._message(user_id, chat_type=chat_type, text=text)
        return await self._feed(Update(update_id=next(self._update_ids), message=message))

    async def send_contact(self, user_id: int, phone: str, contact_user_id: int | None = None) -> list[TelegramMethod]:
        contact = Contact(phone_number=phone, first_name="Test", user_id=contact_user_id or user_id)
        message = self._message(user_id, contact=contact)
        return await self._feed(Update(update_id=next(self._update_ids), message=message))

    async def send_photo_like(self, user_id: int) -> list[TelegramMethod]:
        message = self._message(user_id, caption="a sticker or photo")
        return await self._feed(Update(update_id=next(self._update_ids), message=message))

    async def click(self, user_id: int, data: str | CallbackData) -> list[TelegramMethod]:
        packed = data.pack() if isinstance(data, CallbackData) else data
        origin = Message(
            message_id=next(self._message_ids),
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=self.bot.id, is_bot=True, first_name="SDS Trucking"),
            text="(previous bot message)",
        )
        query = CallbackQuery(
            id=str(next(self._update_ids)),
            from_user=self.user(user_id),
            chat_instance="ci",
            data=packed,
            message=origin,
        )
        return await self._feed(Update(update_id=next(self._update_ids), callback_query=query))


# ------------------------------------------------------------------ inspection helpers


def outgoing_texts(requests: list[TelegramMethod], chat_id: int | None = None) -> list[str]:
    out = []
    for r in requests:
        if isinstance(r, (SendMessage, EditMessageText)) and (chat_id is None or r.chat_id == chat_id):
            out.append(r.text)
    return out


def last_text(requests: list[TelegramMethod]) -> str:
    texts = outgoing_texts(requests)
    assert texts, f"no message sent; requests were: {[type(r).__name__ for r in requests]}"
    return texts[-1]


def alerts(requests: list[TelegramMethod]) -> list[str]:
    return [r.text for r in requests if isinstance(r, AnswerCallbackQuery) and r.text]


def button_texts(requests: list[TelegramMethod]) -> list[str]:
    for r in reversed(requests):
        markup = getattr(r, "reply_markup", None)
        if markup is not None and hasattr(markup, "inline_keyboard"):
            return [b.text for row in markup.inline_keyboard for b in row]
        if markup is not None and hasattr(markup, "keyboard"):
            return [b.text for row in markup.keyboard for b in row]
    return []


def sent_to(requests: list[TelegramMethod], chat_id: int) -> list[SendMessage]:
    return [r for r in requests if isinstance(r, SendMessage) and r.chat_id == chat_id]


Predicate = Callable[[TelegramMethod], bool]
