from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot import faq_manager, config
from bot.keyboards.user_kb import faq_categories_kb, faq_items_kb, faq_item_kb
from bot.keyboards.admin_kb import (
    admin_faq_main_kb,
    admin_faq_categories_kb,
    admin_faq_category_kb,
    admin_faq_item_kb,
    confirm_kb,
)

router = Router()

def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

# ═══════════════════════════════════════════════════════════════════════════════
# FSM States
# ═══════════════════════════════════════════════════════════════════════════════

class FaqAdminStates(StatesGroup):
    waiting_cat_name = State()
    waiting_item_cat = State()
    waiting_item_question = State()
    waiting_item_answer = State()
    waiting_edit_question = State()
    waiting_edit_answer = State()

# ═══════════════════════════════════════════════════════════════════════════════
# USER: /faq command and callbacks
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("faq"), F.chat.type == "private")
async def cmd_faq(message: Message):
    categories = faq_manager.get_categories()
    if not categories:
        await message.answer("📭 FAQ пока пуст.")
        return
    await message.answer("📚 <b>Раздел FAQ</b>\n\nВыберите категорию:", reply_markup=faq_categories_kb(), parse_mode="HTML")

@router.callback_query(F.data == "faq:main")
async def cb_faq_main(callback: CallbackQuery):
    categories = faq_manager.get_categories()
    if not categories:
        await callback.answer("FAQ пока пуст.", show_alert=True)
        return
    await callback.message.edit_text(
        "📚 <b>Раздел FAQ</b>\n\nВыберите категорию:",
        reply_markup=faq_categories_kb(),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data == "faq:close")
async def cb_faq_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data.startswith("faq:cat:"))
async def cb_faq_category(callback: CallbackQuery):
    cat_id = callback.data.split(":", 2)[2]
    cat = faq_manager.get_category(cat_id)
    if cat is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    items = cat.get("items", [])
    if not items:
        await callback.answer("В этой категории пока нет вопросов.", show_alert=True)
        return
    await callback.message.edit_text(
        f"📂 <b>{cat['name']}</b>\n\nВыберите вопрос:",
        reply_markup=faq_items_kb(cat_id),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("faq:item:"))
async def cb_faq_item(callback: CallbackQuery):
    parts = callback.data.split(":")
    # faq:item:cat_id:item_id
    cat_id = parts[2]
    item_id = parts[3]
    item = faq_manager.get_item(cat_id, item_id)
    if item is None:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"❓ <b>{item['q']}</b>\n\n💡 {item['a']}",
        reply_markup=faq_item_kb(cat_id),
        parse_mode="HTML",
    )
    await callback.answer()

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN: /admin_faq command and callbacks
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("admin_faq"), F.chat.type == "private")
async def cmd_admin_faq(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа.")
        return
    await message.answer("🛠 <b>Управление FAQ</b>", reply_markup=admin_faq_main_kb(), parse_mode="HTML")

# ── Admin FAQ callbacks ───────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_faq:main")
async def cb_adm_main(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("🛠 <b>Управление FAQ</b>", reply_markup=admin_faq_main_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "adm_faq:close")
async def cb_adm_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "adm_faq:list")
async def cb_adm_list(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        "📋 <b>Категории FAQ</b>",
        reply_markup=admin_faq_categories_kb(),
        parse_mode="HTML",
    )
    await callback.answer()

# ── Add category ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_faq:add_cat")
async def cb_adm_add_cat(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    await state.set_state(FaqAdminStates.waiting_cat_name)
    await callback.message.edit_text(
        "✏️ Введите название новой категории:\n\n/cancel — отмена"
    )
    await callback.answer()

@router.message(FaqAdminStates.waiting_cat_name, F.chat.type == "private")
async def fsm_cat_name(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=admin_faq_main_kb())
        return
    name = message.text.strip()
    if not name:
        await message.answer("⚠️ Название не может быть пустым.")
        return
    cat_id = faq_manager.add_category(name)
    await state.clear()
    await message.answer(
        f"✅ Категория «{name}» добавлена.",
        reply_markup=admin_faq_category_kb(cat_id),
    )

# ── View category ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_faq:cat:"))
async def cb_adm_category(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    cat_id = callback.data.split(":", 2)[2]
    cat = faq_manager.get_category(cat_id)
    if cat is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    await callback.message.edit_text(
        f"📂 <b>{cat['name']}</b>\n\nВопросов: {len(cat.get('items', []))}",
        reply_markup=admin_faq_category_kb(cat_id),
        parse_mode="HTML",
    )
    await callback.answer()

# ── Delete category ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_faq:del_cat:"))
async def cb_adm_del_cat(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    cat_id = callback.data.split(":", 2)[2]
    cat = faq_manager.get_category(cat_id)
    if cat is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🗑 Удалить категорию «{cat['name']}» и все её вопросы?",
        reply_markup=confirm_kb(
            yes_data=f"adm_faq:del_cat_yes:{cat_id}",
            no_data=f"adm_faq:cat:{cat_id}",
        ),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("adm_faq:del_cat_yes:"))
async def cb_adm_del_cat_yes(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    cat_id = callback.data.split(":", 2)[2]
    faq_manager.delete_category(cat_id)
    await callback.message.edit_text(
        "✅ Категория удалена.",
        reply_markup=admin_faq_categories_kb(),
    )
    await callback.answer()

# ── Add item ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_faq:add_item:"))
async def cb_adm_add_item(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    cat_id = callback.data.split(":", 2)[2]
    await state.update_data(cat_id=cat_id)
    await state.set_state(FaqAdminStates.waiting_item_question)
    await callback.message.edit_text("✏️ Введите текст вопроса:\n\n/cancel — отмена")
    await callback.answer()

@router.message(FaqAdminStates.waiting_item_question, F.chat.type == "private")
async def fsm_item_question(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=admin_faq_main_kb())
        return
    await state.update_data(question=message.text.strip())
    await state.set_state(FaqAdminStates.waiting_item_answer)
    await message.answer("✏️ Теперь введите текст ответа:\n\n/cancel — отмена")

@router.message(FaqAdminStates.waiting_item_answer, F.chat.type == "private")
async def fsm_item_answer(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=admin_faq_main_kb())
        return
    data = await state.get_data()
    cat_id = data["cat_id"]
    question = data["question"]
    answer = message.text.strip()
    item_id = faq_manager.add_item(cat_id, question, answer)
    await state.clear()
    if item_id:
        await message.answer(
            f"✅ Вопрос добавлен.\n\n❓ <b>{question}</b>\n\n💡 {answer}",
            reply_markup=admin_faq_category_kb(cat_id),
            parse_mode="HTML",
        )
    else:
        await message.answer("⚠️ Не удалось добавить вопрос.", reply_markup=admin_faq_main_kb())

# ── View item ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_faq:item:"))
async def cb_adm_item(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    parts = callback.data.split(":")
    cat_id = parts[2]
    item_id = parts[3]
    item = faq_manager.get_item(cat_id, item_id)
    if item is None:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"❓ <b>{item['q']}</b>\n\n💡 {item['a']}",
        reply_markup=admin_faq_item_kb(cat_id, item_id),
        parse_mode="HTML",
    )
    await callback.answer()

# ── Edit item ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_faq:edit:"))
async def cb_adm_edit(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    parts = callback.data.split(":")
    cat_id = parts[2]
    item_id = parts[3]
    await state.update_data(cat_id=cat_id, item_id=item_id)
    await state.set_state(FaqAdminStates.waiting_edit_question)
    item = faq_manager.get_item(cat_id, item_id)
    await callback.message.edit_text(
        f"✏️ Введите новый текст вопроса:\n(Текущий: {item['q']})\n\n/cancel — отмена"
    )
    await callback.answer()

@router.message(FaqAdminStates.waiting_edit_question, F.chat.type == "private")
async def fsm_edit_question(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=admin_faq_main_kb())
        return
    await state.update_data(new_question=message.text.strip())
    await state.set_state(FaqAdminStates.waiting_edit_answer)
    await message.answer("✏️ Теперь введите новый текст ответа:\n\n/cancel — отмена")

@router.message(FaqAdminStates.waiting_edit_answer, F.chat.type == "private")
async def fsm_edit_answer(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=admin_faq_main_kb())
        return
    data = await state.get_data()
    cat_id = data["cat_id"]
    item_id = data["item_id"]
    new_q = data["new_question"]
    new_a = message.text.strip()
    success = faq_manager.edit_item(cat_id, item_id, new_q, new_a)
    await state.clear()
    if success:
        await message.answer(
            f"✅ Вопрос обновлён.\n\n❓ <b>{new_q}</b>\n\n💡 {new_a}",
            reply_markup=admin_faq_item_kb(cat_id, item_id),
            parse_mode="HTML",
        )
    else:
        await message.answer("⚠️ Не удалось обновить вопрос.", reply_markup=admin_faq_main_kb())

# ── Delete item ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_faq:del_item:"))
async def cb_adm_del_item(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    parts = callback.data.split(":")
    cat_id = parts[2]
    item_id = parts[3]
    item = faq_manager.get_item(cat_id, item_id)
    if item is None:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🗑 Удалить вопрос?\n\n❓ {item['q']}",
        reply_markup=confirm_kb(
            yes_data=f"adm_faq:del_item_yes:{cat_id}:{item_id}",
            no_data=f"adm_faq:item:{cat_id}:{item_id}",
        ),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("adm_faq:del_item_yes:"))
async def cb_adm_del_item_yes(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    parts = callback.data.split(":")
    cat_id = parts[2]
    item_id = parts[3]
    faq_manager.delete_item(cat_id, item_id)
    await callback.message.edit_text(
        "✅ Вопрос удалён.",
        reply_markup=admin_faq_category_kb(cat_id),
    )
    await callback.answer()