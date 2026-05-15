from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart

from bot import database, config
from bot.keyboards.user_kb import main_menu_kb, admin_menu_kb

router = Router()

# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    user_id = message.from_user.id
    is_admin = user_id in config.ADMIN_IDS

    await message.answer(
        "👋 Привет! Это бот поддержки.\n\n"
        "Напишите ваш вопрос, и наш модератор ответит вам как можно скорее.\n"
        "Или воспользуйтесь разделом FAQ — возможно, ответ уже есть там.",
        reply_markup=admin_menu_kb() if is_admin else main_menu_kb(),
    )

# ── User messages → forward to admin topic ────────────────────────────────────

@router.message(F.chat.type == "private")
async def user_message(message: Message, bot: Bot):
    user = message.from_user
    user_id = user.id

    # Ignore callback ghost messages from inline buttons (no text/media)
    if not any([
        message.text, message.photo, message.video,
        message.document, message.voice, message.sticker,
        message.audio, message.animation,
    ]):
        return

    ticket = await database.get_active_ticket_by_user(user_id)

    if ticket is None:
        # ── Create a brand new topic for this request ──────────────────────
        username_part = f"@{user.username}" if user.username else f"id:{user_id}"
        topic_name = f"{user.full_name} ({username_part})"

        try:
            forum_topic = await bot.create_forum_topic(
                chat_id=config.GROUP_ID,
                name=topic_name[:128],
            )
        except Exception:
            await message.answer("⚠️ Не удалось создать тикет. Попробуйте позже.")
            return

        thread_id = forum_topic.message_thread_id
        await database.create_ticket(user_id, thread_id, user.username)

        info_text = (
            f"🎫 <b>Новый тикет</b>\n\n"
            f"👤 <b>Пользователь:</b> {user.full_name}\n"
            f"🔗 <b>Username:</b> {username_part}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            f"Используйте /claim чтобы взять тикет, /close чтобы закрыть.\n"
            f"Используйте /silent чтобы включить тихий режим (ответы не идут юзеру)."
        )
        await bot.send_message(
            chat_id=config.GROUP_ID,
            message_thread_id=thread_id,
            text=info_text,
            parse_mode="HTML",
        )
    else:
        thread_id = ticket["thread_id"]

    await _forward_to_topic(bot, message, thread_id)

async def _forward_to_topic(bot: Bot, message: Message, thread_id: int):
    """Forward any type of message to the admin group topic."""
    try:
        if message.text:
            await bot.send_message(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                text=message.text,
            )
        elif message.photo:
            await bot.send_photo(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                photo=message.photo[-1].file_id,
                caption=message.caption or None,
            )
        elif message.video:
            await bot.send_video(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                video=message.video.file_id,
                caption=message.caption or None,
            )
        elif message.audio:
            await bot.send_audio(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                audio=message.audio.file_id,
                caption=message.caption or None,
            )
        elif message.animation:
            await bot.send_animation(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                animation=message.animation.file_id,
                caption=message.caption or None,
            )
        elif message.document:
            await bot.send_document(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                document=message.document.file_id,
                caption=message.caption or None,
            )
        elif message.voice:
            await bot.send_voice(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                voice=message.voice.file_id,
            )
        elif message.sticker:
            await bot.send_sticker(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                sticker=message.sticker.file_id,
            )
        else:
            await bot.send_message(
                chat_id=config.GROUP_ID,
                message_thread_id=thread_id,
                text="[неподдерживаемый тип сообщения]",
            )
    except Exception:
        pass