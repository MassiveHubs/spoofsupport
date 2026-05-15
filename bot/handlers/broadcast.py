from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot import database, config
from bot.keyboards.user_kb import admin_menu_kb

router = Router()

def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

class BroadcastFSM(StatesGroup):
    waiting_message = State()

# ── Admin panel callbacks ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔️ Нет доступа.", show_alert=True)
        return

    await call.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение, которое нужно разослать всем пользователям.\n"
        "Поддерживаются текст, фото, видео, документы, голос.\n\n"
        "Отправьте /cancel чтобы отменить.",
        parse_mode="HTML",
    )
    await state.set_state(BroadcastFSM.waiting_message)
    await call.answer()

@router.callback_query(F.data == "admin:stats")
async def cb_stats(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔️ Нет доступа.", show_alert=True)
        return

    stats = await database.get_ticket_stats()
    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"🎫 Всего тикетов: <b>{stats['total']}</b>\n"
        f"🟢 Открытых: <b>{stats['open']}</b>\n"
        f"🔒 Закрытых: <b>{stats['closed']}</b>\n"
        f"👥 Уникальных пользователей: <b>{stats['users']}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )
    await call.answer()

# ── Cancel broadcast ───────────────────────────────────────────────────────────

@router.message(F.text == "/cancel", F.chat.type == "private", BroadcastFSM.waiting_message)
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.", reply_markup=admin_menu_kb())

# ── Receive broadcast message and send ────────────────────────────────────────

@router.message(F.chat.type == "private", BroadcastFSM.waiting_message)
async def do_broadcast(message: Message, bot: Bot, state: FSMContext):
    await state.clear()

    user_ids = await database.get_all_user_ids()
    if not user_ids:
        await message.answer("ℹ️ Нет пользователей для рассылки.", reply_markup=admin_menu_kb())
        return

    sent = 0
    failed = 0

    status_msg = await message.answer(f"⏳ Рассылка началась... 0 / {len(user_ids)}")

    for uid in user_ids:
        try:
            if message.text:
                await bot.send_message(chat_id=uid, text=message.text)
            elif message.photo:
                await bot.send_photo(
                    chat_id=uid,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or None,
                )
            elif message.video:
                await bot.send_video(
                    chat_id=uid,
                    video=message.video.file_id,
                    caption=message.caption or None,
                )
            elif message.document:
                await bot.send_document(
                    chat_id=uid,
                    document=message.document.file_id,
                    caption=message.caption or None,
                )
            elif message.voice:
                await bot.send_voice(chat_id=uid, voice=message.voice.file_id)
            elif message.animation:
                await bot.send_animation(
                    chat_id=uid,
                    animation=message.animation.file_id,
                    caption=message.caption or None,
                )
            else:
                failed += 1
                continue
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена.</b>\n\n"
        f"📤 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )