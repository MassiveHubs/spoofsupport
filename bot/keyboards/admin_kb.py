from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import faq_manager

# ── FAQ admin keyboards ───────────────────────────────────────────────────────

def admin_faq_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список категорий", callback_data="adm_faq:list")],
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="adm_faq:add_cat")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm_faq:close")],
    ])

def admin_faq_categories_kb() -> InlineKeyboardMarkup:
    categories = faq_manager.get_categories()
    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"adm_faq:cat:{cat['id']}")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="adm_faq:add_cat")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_faq:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_faq_category_kb(cat_id: str) -> InlineKeyboardMarkup:
    cat = faq_manager.get_category(cat_id)
    if cat is None:
        return admin_faq_categories_kb()
    buttons = [
        [InlineKeyboardButton(text=f"❓ {item['q'][:40]}", callback_data=f"adm_faq:item:{cat_id}:{item['id']}")]
        for item in cat.get("items", [])
    ]
    buttons.append([InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"adm_faq:add_item:{cat_id}")])
    buttons.append([InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"adm_faq:del_cat:{cat_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_faq:list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_faq_item_kb(cat_id: str, item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"adm_faq:edit:{cat_id}:{item_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_faq:del_item:{cat_id}:{item_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_faq:cat:{cat_id}")],
    ])

def confirm_kb(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
            InlineKeyboardButton(text="❌ Нет", callback_data=no_data),
        ]
    ])