from pymongo.collection import Collection

class AnalyticsManager:
    def __init__(self, analytics_col: Collection):
        self.analytics_col = analytics_col
        self.init_analytics()

    # ===============================
    # INIT ANALYTICS
    # ===============================
    def init_analytics(self):
        if self.analytics_col.count_documents({"type": "analytics"}) == 0:
            self.analytics_col.insert_one({
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
    def track_search(self, query: str):
        self.analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {"total_searches": 1, f"product_search.{query.lower()}": 1}}
        )

    # ===============================
    # TRACK QUESTION
    # ===============================
    def track_question(self, question: str):
        self.analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {f"most_questions.{question}": 1}}
        )

    # ===============================
    # TRACK PRODUCT CLICK
    # ===============================
    def track_click(self, product_id: str):
        self.analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {"total_clicks": 1, f"product_clicks.{product_id}": 1}}
        )

    # ===============================
    # TRACK PRICE UPDATE
    # ===============================
    def track_price_update(self, product_id: str):
        self.analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {f"price_updates.{product_id}": 1}}
        )

    # ===============================
    # TRACK LANGUAGE
    # ===============================
    def track_language(self, language: str):
        self.analytics_col.update_one(
            {"type": "analytics"},
            {"$inc": {f"supported_languages.{language.lower()}": 1}}
        )

    # ===============================
    # GET ANALYTICS
    # ===============================
    def get_analytics(self):
        data = self.analytics_col.find_one({"type": "analytics"})
        if data and "_id" in data:
            data["_id"] = str(data["_id"])
        return data
