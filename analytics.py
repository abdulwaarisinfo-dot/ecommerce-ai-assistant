# analytics.py
# ============================================================
# ANALYTICS ENGINE — Track searches, clicks, languages, prices
# ============================================================

import logging
from typing import Optional
from pymongo.collection import Collection

logger = logging.getLogger("Analytics")

# ============================================================
# INIT ANALYTICS DOCUMENT
# ============================================================

def init_analytics(analytics_col: Optional[Collection]) -> None:
    """
    Ensures the analytics document exists in MongoDB.
    Creates a fresh one if none is found.
    """
    if analytics_col is None:
        logger.warning("Analytics collection not available — skipping init.")
        return

    try:
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
            logger.info("Analytics document initialized.")
    except Exception as e:
        logger.error(f"Analytics init error: {e}")


# ============================================================
# TRACK SEARCH QUERY
# ============================================================

def track_search(analytics_col: Optional[Collection], query: str) -> None:
    """
    Increments the global search counter and logs the query.
    Sanitizes the key for MongoDB field name compatibility.
    """
    if analytics_col is None or not query:
        return

    try:
        safe_key = _sanitize_key(query.lower().strip())
        analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {
                "total_searches": 1,
                f"product_search.{safe_key}": 1
            }},
            upsert=True
        )
    except Exception as e:
        logger.error(f"track_search error: {e}")


# ============================================================
# TRACK CHATBOT QUESTION
# ============================================================

def track_question(analytics_col: Optional[Collection], question: str) -> None:
    """
    Records questions users ask the chatbot.
    Useful for discovering FAQ gaps and new intents.
    """
    if analytics_col is None or not question:
        return

    try:
        safe_key = _sanitize_key(question.strip())
        analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {f"most_questions.{safe_key}": 1}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"track_question error: {e}")


# ============================================================
# TRACK PRODUCT CLICK
# ============================================================

def track_click(analytics_col: Optional[Collection], product_id: str) -> None:
    """
    Logs every time a user clicks on a product card.
    Tracks both global click totals and per-product counts.
    """
    if analytics_col is None or not product_id:
        return

    try:
        safe_key = _sanitize_key(product_id.strip())
        analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {
                "total_clicks": 1,
                f"product_clicks.{safe_key}": 1
            }},
            upsert=True
        )
    except Exception as e:
        logger.error(f"track_click error: {e}")


# ============================================================
# TRACK PRICE UPDATE
# ============================================================

def track_price_update(analytics_col: Optional[Collection], product_id: str) -> None:
    """
    Logs how many times a product's price has been updated.
    Useful for auditing frequent price changes.
    """
    if analytics_col is None or not product_id:
        return

    try:
        safe_key = _sanitize_key(product_id.strip())
        analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {f"price_updates.{safe_key}": 1}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"track_price_update error: {e}")


# ============================================================
# TRACK LANGUAGE
# ============================================================

def track_language(analytics_col: Optional[Collection], language: str) -> None:
    """
    Records which language each user interacts in.
    Supports: en, ur, de (and any future language code).
    """
    if analytics_col is None or not language:
        return

    try:
        lang_code = language.lower().strip()
        analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {f"supported_languages.{lang_code}": 1}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"track_language error: {e}")


# ============================================================
# GET ANALYTICS DATA
# ============================================================

def get_analytics_data(analytics_col: Optional[Collection]) -> dict:
    """
    Fetches the full analytics document from MongoDB.
    Converts ObjectId to string for JSON serialization.
    Returns a safe empty structure on failure.
    """
    if analytics_col is None:
        logger.warning("Analytics collection not available.")
        return _empty_analytics()

    try:
        data = analytics_col.find_one({"type": "analytics"})

        if not data:
            return _empty_analytics()

        # Serialize MongoDB ObjectId
        if "_id" in data:
            data["_id"] = str(data["_id"])

        return data

    except Exception as e:
        logger.error(f"get_analytics_data error: {e}")
        return _empty_analytics()


# ============================================================
# PRIVATE HELPERS
# ============================================================

def _sanitize_key(key: str) -> str:
    """
    Strips characters that MongoDB disallows in field names:
    dots (.), dollar signs ($), and null bytes.
    Also truncates to 200 chars to avoid oversized keys.
    """
    key = key.replace(".", "_").replace("$", "").replace("\x00", "")
    return key[:200]


def _empty_analytics() -> dict:
    """Returns a safe fallback analytics payload."""
    return {
        "type": "analytics",
        "total_searches": 0,
        "total_clicks": 0,
        "most_questions": {},
        "product_search": {},
        "product_clicks": {},
        "price_updates": {},
        "supported_languages": {}
    }
