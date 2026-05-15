import json
import os
import uuid

FAQ_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "faq.json")

def _load() -> dict:
    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: dict) -> None:
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_categories() -> list[dict]:
    return _load().get("categories", [])

def get_category(cat_id: str) -> dict | None:
    for cat in get_categories():
        if cat["id"] == cat_id:
            return cat
    return None

def get_item(cat_id: str, item_id: str) -> dict | None:
    cat = get_category(cat_id)
    if cat is None:
        return None
    for item in cat.get("items", []):
        if item["id"] == item_id:
            return item
    return None

def add_category(name: str) -> str:
    data = _load()
    new_id = str(uuid.uuid4())[:8]
    data["categories"].append({"id": new_id, "name": name, "items": []})
    _save(data)
    return new_id

def add_item(cat_id: str, question: str, answer: str) -> str | None:
    data = _load()
    for cat in data["categories"]:
        if cat["id"] == cat_id:
            new_id = str(uuid.uuid4())[:8]
            cat["items"].append({"id": new_id, "q": question, "a": answer})
            _save(data)
            return new_id
    return None

def edit_item(cat_id: str, item_id: str, question: str, answer: str) -> bool:
    data = _load()
    for cat in data["categories"]:
        if cat["id"] == cat_id:
            for item in cat["items"]:
                if item["id"] == item_id:
                    item["q"] = question
                    item["a"] = answer
                    _save(data)
                    return True
    return False

def delete_item(cat_id: str, item_id: str) -> bool:
    data = _load()
    for cat in data["categories"]:
        if cat["id"] == cat_id:
            before = len(cat["items"])
            cat["items"] = [i for i in cat["items"] if i["id"] != item_id]
            if len(cat["items"]) < before:
                _save(data)
                return True
    return False

def delete_category(cat_id: str) -> bool:
    data = _load()
    before = len(data["categories"])
    data["categories"] = [c for c in data["categories"] if c["id"] != cat_id]
    if len(data["categories"]) < before:
        _save(data)
        return True
    return False