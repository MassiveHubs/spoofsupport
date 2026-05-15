from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import faq_manager

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 FAQ", callback_data="faq:main")],
        [InlineKeyboardButton(text="🔗 Исходники бота", url="https://github.com/MassiveHubs/spoofsupport")],
    ])

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 FAQ", callback_data="faq:main")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🔗 Исходники бота", url="https://github.com/MassiveHubs/spoofsupport")],
    ])

def faq_categories_kb() -> InlineKeyboardMarkup:
    categories = faq_manager.get_categories()
    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"faq:cat:{cat['id']}")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="faq:close")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def faq_items_kb(cat_id: str) -> InlineKeyboardMarkup:
    cat = faq_manager.get_category(cat_id)
    if cat is None:
        return faq_categories_kb()
    buttons = [
        [InlineKeyboardButton(text=item["q"], callback_data=f"faq:item:{cat_id}:{item['id']}")]
        for item in cat.get("items", [])
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="faq:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def faq_item_kb(cat_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к вопросам", callback_data=f"faq:cat:{cat_id}")],
        [InlineKeyboardButton(text="🏠 Главное меню FAQ", callback_data="faq:main")],
    ])