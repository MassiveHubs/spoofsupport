from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot import database, config

router = Router()

def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

# ── /claim ────────────────────────────────────────────────────────────────────

@router.message(Command("claim"), F.chat.id == config.GROUP_ID)
async def cmd_claim(message: Message):
    user = message.from_user
    if not _is_admin(user.id):
        await message.reply("⛔️ Только модераторы могут клеймить тикеты.")
        return

    thread_id = message.message_thread_id
    if thread_id is None:
        await message.reply("⚠️ Эту команду нужно использовать внутри топика тикета.")
        return

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await message.reply("⚠️ Этот топик не является тикетом поддержки.")
        return

    if ticket["claimed_by"] is not None and ticket["claimed_by"] != user.id:
        await message.reply(
            f"⛔️ Тикет уже заклеймлен другим модератором (ID: {ticket['claimed_by']})."
        )
        return

    success = await database.claim_ticket(thread_id, user.id)
    if success:
        username = f"@{user.username}" if user.username else user.full_name
        await message.reply(
            f"✅ Тикет заклеймлен модератором {username}.\n"
            f"Теперь только он может отвечать здесь.\n"
            f"Используйте /add @username чтобы добавить коллегу.\n"
            f"Используйте /unclaim чтобы снять клейм."
        )
    else:
        await message.reply("⚠️ Не удалось заклеймить тикет.")

# ── /unclaim ──────────────────────────────────────────────────────────────────

@router.message(Command("unclaim"), F.chat.id == config.GROUP_ID)
async def cmd_unclaim(message: Message):
    user = message.from_user
    if not _is_admin(user.id):
        await message.reply("⛔️ Только модераторы могут снимать клейм.")
        return

    thread_id = message.message_thread_id
    if thread_id is None:
        await message.reply("⚠️ Эту команду нужно использовать внутри топика тикета.")
        return

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await message.reply("⚠️ Этот топик не является тикетом поддержки.")
        return

    if ticket["claimed_by"] is None:
        await message.reply("ℹ️ Тикет не заклеймлен.")
        return

    success = await database.unclaim_ticket(thread_id, user.id)
    if success:
        await message.reply("🔓 Клейм снят. Теперь любой модератор может отвечать.")
    else:
        # Force unclaim for any admin
        async with __import__("aiosqlite").connect(database.DB_PATH) as db:
            await db.execute(
                "UPDATE tickets SET claimed_by = NULL WHERE thread_id = ?", (thread_id,)
            )
            await db.execute(
                "DELETE FROM allowed_users WHERE thread_id = ?", (thread_id,)
            )
            await db.commit()
        await message.reply("🔓 Клейм принудительно снят.")

# ── /add @username ────────────────────────────────────────────────────────────

async def _build_member_picker(bot: Bot, thread_id: int) -> InlineKeyboardMarkup:
    """Return inline keyboard with all non-bot group members (admins + tracked users)."""
    buttons = []

    # Get admins from Telegram API
    try:
        admins = await bot.get_chat_administrators(config.GROUP_ID)
        for member in admins:
            u = member.user
            if u.is_bot:
                continue
            label = f"@{u.username}" if u.username else u.full_name
            buttons.append([InlineKeyboardButton(
                text=label,
                callback_data=f"adduser:{thread_id}:{u.id}:{label}"
            )])
    except Exception:
        pass

    # Also add any tracked users from our DB who are not already in the list
    try:
        admin_ids = {btn[0].callback_data.split(":")[2] for btn in buttons}
        tracked = await database.get_all_user_ids()
        for uid in tracked:
            if str(uid) not in admin_ids:
                buttons.append([InlineKeyboardButton(
                    text=f"👤 ID {uid}",
                    callback_data=f"adduser:{thread_id}:{uid}:ID {uid}"
                )])
    except Exception:
        pass

    if not buttons:
        return None

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"adduser_cancel:{thread_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("add"), F.chat.id == config.GROUP_ID)
async def cmd_add(message: Message, bot: Bot):
    user = message.from_user
    if not _is_admin(user.id):
        await message.reply("⛔️ Только модераторы могут добавлять участников.")
        return

    thread_id = message.message_thread_id
    if thread_id is None:
        await message.reply("⚠️ Эту команду нужно использовать внутри топика тикета.")
        return

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await message.reply("⚠️ Этот топик не является тикетом поддержки.")
        return

    if ticket["claimed_by"] is None:
        await message.reply("ℹ️ Тикет не заклеймлен — все модераторы уже могут писать.")
        return

    if ticket["claimed_by"] != user.id:
        await message.reply("⛔️ Добавлять участников может только тот, кто заклеймил тикет.")
        return

    args = message.text.split(maxsplit=1)

    # ── No argument: show picker ──────────────────────────────────────────────
    if len(args) < 2 or not args[1].strip():
        kb = await _build_member_picker(bot, thread_id)
        if kb:
            await message.reply(
                "👥 <b>Выберите участника для добавления:</b>",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.reply(
                "⚠️ Не удалось получить список участников.\n"
                "Укажите username вручную: /add @username"
            )
        return

    # ── Username provided: try to resolve ─────────────────────────────────────
    target_username = args[1].lstrip("@").strip()
    target_id = await _resolve_username(bot, target_username)

    if target_id is None:
        # Resolution failed — show picker
        kb = await _build_member_picker(bot, thread_id)
        if kb:
            await message.reply(
                f"⚠️ Не удалось найти <code>@{target_username}</code> напрямую.\n\n"
                f"👥 <b>Выберите участника из списка:</b>",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.reply(
                f"⚠️ Не удалось найти пользователя @{target_username}.\n"
                f"Убедитесь, что он писал боту или является участником группы."
            )
        return

    await database.add_allowed_user(thread_id, target_id)
    await message.reply(f"✅ @{target_username} добавлен в список участников этого тикета.")

# ── Callback: user selected from picker ───────────────────────────────────────

@router.callback_query(F.data.startswith("adduser:"), F.message.chat.id == config.GROUP_ID)
async def cb_adduser(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔️ Нет доступа.", show_alert=True)
        return

    parts = call.data.split(":", 3)
    # format: adduser:{thread_id}:{user_id}:{label}
    if len(parts) < 4:
        await call.answer("⚠️ Ошибка данных.", show_alert=True)
        return

    thread_id = int(parts[1])
    target_id = int(parts[2])
    label = parts[3]

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await call.answer("⚠️ Тикет не найден.", show_alert=True)
        return

    if ticket["claimed_by"] != call.from_user.id:
        await call.answer("⛔️ Только тот, кто заклеймил тикет, может добавлять участников.", show_alert=True)
        return

    await database.add_allowed_user(thread_id, target_id)
    await call.message.edit_text(
        f"✅ <b>{label}</b> добавлен в список участников этого тикета.",
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("adduser_cancel:"), F.message.chat.id == config.GROUP_ID)
async def cb_adduser_cancel(call: CallbackQuery):
    parts = call.data.split(":", 1)
    await call.message.edit_text("❌ Добавление участника отменено.")
    await call.answer()

async def _resolve_username(bot: Bot, username: str) -> int | None:
    """
    Resolve username → user_id.
    1. Check our own DB (stored when ticket was created).
    2. getChatMember from the admin group — works if the user is a member.
    3. getChat fallback — works for public usernames.
    """
    # 1. DB lookup
    user_id = await database.get_user_id_by_username(username)
    if user_id:
        return user_id

    # 2. Try to find in the admin group
    try:
        member = await bot.get_chat_member(config.GROUP_ID, f"@{username}")
        return member.user.id
    except Exception:
        pass

    # 3. Telegram global username lookup
    try:
        chat = await bot.get_chat(f"@{username}")
        return chat.id
    except Exception:
        pass

    return None

# ── /silent ───────────────────────────────────────────────────────────────────

@router.message(Command("silent"), F.chat.id == config.GROUP_ID)
async def cmd_silent(message: Message):
    user = message.from_user
    if not _is_admin(user.id):
        await message.reply("⛔️ Только модераторы могут управлять тихим режимом.")
        return

    thread_id = message.message_thread_id
    if thread_id is None:
        await message.reply("⚠️ Эту команду нужно использовать внутри топика тикета.")
        return

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await message.reply("⚠️ Этот топик не является тикетом поддержки.")
        return

    new_state = await database.toggle_silent(thread_id)
    if new_state:
        await message.reply(
            "🔇 <b>Тихий режим включён.</b>\n"
            "Ваши сообщения в этом топике <b>не будут</b> пересылаться пользователю.\n"
            "Используйте /silent снова чтобы отключить.",
            parse_mode="HTML",
        )
    else:
        await message.reply(
            "🔊 <b>Тихий режим выключен.</b>\n"
            "Ваши сообщения снова пересылаются пользователю.",
            parse_mode="HTML",
        )

# ── /close ────────────────────────────────────────────────────────────────────

@router.message(Command("close"), F.chat.id == config.GROUP_ID)
async def cmd_close(message: Message, bot: Bot):
    user = message.from_user
    if not _is_admin(user.id):
        await message.reply("⛔️ Только модераторы могут закрывать тикеты.")
        return

    thread_id = message.message_thread_id
    if thread_id is None:
        await message.reply("⚠️ Эту команду нужно использовать внутри топика тикета.")
        return

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await message.reply("⚠️ Этот топик не является тикетом поддержки.")
        return

    if ticket["status"] == "closed":
        await message.reply("ℹ️ Тикет уже закрыт.")
        return

    await database.close_ticket(thread_id)

    try:
        await bot.send_message(
            chat_id=ticket["user_id"],
            text="✅ Ваш тикет был закрыт модератором. Если у вас есть ещё вопросы — просто напишите нам.",
        )
    except Exception:
        pass

    try:
        await bot.close_forum_topic(
            chat_id=config.GROUP_ID,
            message_thread_id=thread_id,
        )
    except Exception:
        pass

    await message.reply("🔒 Тикет закрыт.")

# ── /info ─────────────────────────────────────────────────────────────────────

@router.message(Command("info"), F.chat.id == config.GROUP_ID)
async def cmd_info(message: Message):
    thread_id = message.message_thread_id
    if thread_id is None:
        await message.reply("⚠️ Эту команду нужно использовать внутри топика тикета.")
        return

    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        await message.reply("⚠️ Этот топик не является тикетом поддержки.")
        return

    allowed = await database.get_allowed_users(thread_id)
    claimed_str = f"<code>{ticket['claimed_by']}</code>" if ticket["claimed_by"] else "Не заклеймлен"
    allowed_str = ", ".join(f"<code>{u}</code>" for u in allowed) if allowed else "—"
    silent_str = "🔇 Включён" if ticket.get("silent") else "🔊 Выключен"

    await message.reply(
        f"📋 <b>Информация о тикете</b>\n\n"
        f"👤 User ID: <code>{ticket['user_id']}</code>\n"
        f"🧵 Thread ID: <code>{ticket['thread_id']}</code>\n"
        f"📌 Статус: <b>{ticket['status']}</b>\n"
        f"🔒 Заклеймлен: {claimed_str}\n"
        f"👥 Разрешённые: {allowed_str}\n"
        f"🔇 Тихий режим: {silent_str}\n"
        f"📅 Создан: {ticket['created_at']}",
        parse_mode="HTML",
    )

# ── Admin replies in topic → forward to user ──────────────────────────────────

@router.message(F.chat.id == config.GROUP_ID, F.message_thread_id.is_not(None))
async def admin_reply(message: Message, bot: Bot):
    """Forward moderator reply from topic back to the user (unless silent mode is on)."""
    sender = message.from_user
    if sender is None or not _is_admin(sender.id):
        return

    thread_id = message.message_thread_id
    ticket = await database.get_ticket_by_thread(thread_id)
    if ticket is None:
        return

    if ticket["status"] == "closed":
        return

    # Silent mode — messages stay in the topic only
    if ticket.get("silent"):
        return

    user_id = ticket["user_id"]

    try:
        if message.text:
            await bot.send_message(chat_id=user_id, text=message.text)
        elif message.photo:
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption or None,
            )
        elif message.video:
            await bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=message.caption or None,
            )
        elif message.audio:
            await bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=message.caption or None,
            )
        elif message.animation:
            await bot.send_animation(
                chat_id=user_id,
                animation=message.animation.file_id,
                caption=message.caption or None,
            )
        elif message.document:
            await bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=message.caption or None,
            )
        elif message.voice:
            await bot.send_voice(chat_id=user_id, voice=message.voice.file_id)
        elif message.sticker:
            await bot.send_sticker(chat_id=user_id, sticker=message.sticker.file_id)
    except Exception:
        await message.reply("⚠️ Не удалось доставить сообщение пользователю.")