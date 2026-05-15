from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from bot import database, config

class ClaimGuardMiddleware(BaseMiddleware):
    """
    Blocks messages in the admin group topic if the ticket is claimed
    and the sender is not in the allowed_users list.
    Passes through: commands, bot messages, messages outside the group.
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Only care about messages inside the admin group
        if event.chat.id != config.GROUP_ID:
            return await handler(event, data)

        # Not a topic message — skip
        if event.message_thread_id is None:
            return await handler(event, data)

        thread_id = event.message_thread_id
        sender_id = event.from_user.id if event.from_user else None

        if sender_id is None:
            return await handler(event, data)

        # Always allow admins to use commands (they start with /)
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        # Check if ticket is claimed
        ticket = await database.get_ticket_by_thread(thread_id)
        if ticket is None:
            # No ticket → normal group message, not a support topic
            return await handler(event, data)

        claimed_by = ticket.get("claimed_by")
        if claimed_by is None:
            # Not claimed → everyone allowed
            return await handler(event, data)

        # Ticket is claimed — check if sender is allowed
        allowed = await database.is_allowed(thread_id, sender_id)
        if allowed:
            return await handler(event, data)

        # Block the message
        try:
            await event.delete()
        except Exception:
            pass

        try:
            await event.answer(
                "⛔️ Этот тикет заклеймлен. Только назначенный модератор может писать здесь.",
                message_thread_id=thread_id,
            )
        except Exception:
            pass

        return  # Do not call handler