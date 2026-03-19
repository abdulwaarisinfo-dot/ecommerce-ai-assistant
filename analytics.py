from fastapi import Form
from pymongo.collection import Collection

# ===============================
# INIT ANALYTICS
# ===============================
def init_analytics(analytics_col: Collection):
    """
    Initializes analytics collection if empty.
    """
    if analytics_col.count_documents({"type": "analytics"}) == 0:
        analytics_col.insert_one({
            "type": "analytics",
            "total_searches": 0,
            "total_clicks": 0,
            "most_questions": {},
            "product_search": {},
            "product_clicks": {},
            "price_updates": {},
            "supported_languages": {}
        })

# ===============================
# TRACK SEARCH
# ===============================
def track_search(analytics_col: Collection, query: str):
    """
    Track user search queries.
    """
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {"total_searches": 1, f"product_search.{query.lower()}": 1}}
    )

# ===============================
# TRACK QUESTION
# ===============================
def track_question(analytics_col: Collection, question: str):
    """
    Track questions users ask in chatbot.
    """
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {f"most_questions.{question}": 1}}
    )

# ===============================
# TRACK PRODUCT CLICK
# ===============================
def track_click(analytics_col: Collection, product_id: str):
    """
    Track product click events.
    """
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {"total_clicks": 1, f"product_clicks.{product_id}": 1}}
    )

# ===============================
# TRACK PRICE UPDATE
# ===============================
def track_price_update(analytics_col: Collection, product_id: str):
    """
    Track how many times a product's price is updated.
    """
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {f"price_updates.{product_id}": 1}}
    )

# ===============================
# TRACK LANGUAGE
# ===============================
def track_language(analytics_col: Collection, language: str):
    """
    Tracks which language users are using in the chatbot.
    Example: en, ur, hi, ar
    """
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {f"supported_languages.{language.lower()}": 1}}
    )

# ===============================
# GET ANALYTICS DATA
# ===============================
def get_analytics_data(analytics_col: Collection) -> dict:
    """
    Returns analytics data in JSON format.
    """
    data = analytics_col.find_one({"type": "analytics"})
    if "_id" in data:
        data["_id"] = str(data["_id"])
    return data
