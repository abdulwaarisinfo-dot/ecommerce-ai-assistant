from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient

from dotenv import load_dotenv
import os
import logging
from typing import List, Dict, Any, Optional

from langdetect import detect, DetectorFactory
import asyncio
import re 
import certifi
from bson import ObjectId
import random

import analytics
from websocket import router as websocket_router

# ============================================================
# ------------------ INITIAL SETUP ---------------------------
# ============================================================
load_dotenv()
DetectorFactory.seed = 0
logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Chatbot")

# Global State
BOT_DATA: Dict[str, Any] = {}
PRODUCTS_DATA: List[Dict[str, Any]] = []
USER_SESSION_HISTORY: Dict[str, Dict[str, Any]] = {}

app = FastAPI(
    title="AI E-Commerce Chabot", 
    version="2.0",
    docs_url=None,    # This disables /docs
    redoc_url=None,   # This disables /redoc
    openapi_url=None)  # This disables the /openapi.json file)

templates = Jinja2Templates(directory="templates")

# ======================================================
# DATABASE CONNECTION & AUTO-SYNC
# ======================================================

MONGO_URI = os.getenv("MONGO_URI", "")

logger = logging.getLogger(__name__)

PRODUCTS_DATA = []
BOT_DATA = {}

MONGO_URI = os.getenv("MONGO_URI", "")

try:
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000
    )

    db = client["ecommerce"]

    # Collections
    products_col = db["products"]
    meta_col = db["bot_metadata"]
    analytics_col = db["analytics"]

    # Test connection
    client.admin.command("ping")

    logger.info("MongoDB connected successfully")

except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    products_col = None
    meta_col = None
    analytics_col = None

# ======================================================
# REALTIME DATA LOADER
# ======================================================

def load_data_realtime():
    """
    Reads latest products and bot configs from MongoDB
    and syncs them to memory.
    """

    global PRODUCTS_DATA, BOT_DATA

    if products_col is None or meta_col is None:
        logger.error("Database collections not initialized")
        return

    try:

        # ------------------------------------------------
        # PRODUCT SYNC
        # ------------------------------------------------
        products_cursor = products_col.find({})
        temp_products = []

        for product in products_cursor:

            if "_id" in product:
                product["_id"] = str(product["_id"])

            temp_products.append(product)

        PRODUCTS_DATA = temp_products

        # ------------------------------------------------
        # BOT METADATA SYNC
        # ------------------------------------------------

        # Try to load config document
        meta = meta_col.find_one({"type": "config"})

        # If not found, load first document
        if not meta:
            meta = meta_col.find_one({})

        if meta:

            if "_id" in meta:
                meta["_id"] = str(meta["_id"])

            BOT_DATA = meta

        else:
            # Safe fallback
            BOT_DATA = {
                "supported_languages": ["en"],
                "initial_message": {
                    "en": "Hello! How can I help you today?"
                },
                "faq": {},
                "smart_suggestions": {}
            }

        logger.info(
            f"Data Sync Completed | Products: {len(PRODUCTS_DATA)}"
        )

    except Exception as e:
        logger.error(f"Auto-load Error: {e}")

# ======================================================
# OPTIONAL: AUTO LOAD ON STARTUP
# ======================================================

def init_database_sync():
    """
    Initialize database data on server start.
    """
    load_data_realtime()

# ============================================================
# ------------------ LANGUAGE DETECTION ----------------------
# ============================================================
from keywords import (
    detect_language, 
    COLOR_KEYWORDS, 
    MATERIAL_KEYWORDS, 
    CATEGORY_KEYWORDS, 
    INTENT_KEYWORDS
)

def smart_match(text, keyword_dict):
    """Checks which keys match based on the synonym lists."""
    text = text.lower()
    matches = []
    for category, synonyms in keyword_dict.items():
        if any(synonym in text for synonym in synonyms):
            matches.append(category)
    return matches

def process_user_query(query):
    # 1. Detect Language
    lang = detect_language(query)
    
    # 2. Extract Data using your dictionaries
    extracted_data = {
        "language": lang,
        "colors": smart_match(query, COLOR_KEYWORDS),
        "materials": smart_match(query, MATERIAL_KEYWORDS),
        "categories": smart_match(query, CATEGORY_KEYWORDS),
        "intents": smart_match(query, INTENT_KEYWORDS)
    }
    
    return extracted_data

# ============================================================
# ---------------- HELPER FUNCTIONS -------------------------
# ============================================================

def parse_price_range(query: str) -> Dict[str, float]:
    query_lower = (
        query.lower()
        .replace('$', '')
        .replace('€', '')
        .replace('rs', '')
        .replace('pkr', '')
    )

    price_range: Dict[str, float] = {}

    match_under = re.search(r'(under|below|less than|کم|weniger als|unter)\s*(\d+)', query_lower)
    match_over = re.search(r'(over|above|greater than|زیادہ|über|mehr als)\s*(\d+)', query_lower)

    if match_under:
        try:
            price_range["max"] = float(match_under.group(2))
        except:
            pass

    if match_over:
        try:
            price_range["min"] = float(match_over.group(2))
        except:
            pass

    return price_range

def score_product_relevance(query: str, product: Dict[str, Any], price_range: Dict[str, float]) -> float:
    query_lower = query.lower()
    score = 0.0

    field_text = " ".join(
        [str(product.get(f, '')).lower() for f in ['title', 'description', 'color', 'material', 'category']]
    )
    
    query_words = set(re.findall(r'\w+', query_lower))
    product_words = set(re.findall(r'\w+', field_text))

    score += len(query_words.intersection(product_words)) * 0.8

    for category, kws in CATEGORY_KEYWORDS.items():
        if any(kw in query_lower for kw in kws) and category in field_text:
            score += 3.0

    for color, kws in COLOR_KEYWORDS.items():
        if any(kw in query_lower for kw in kws) and color in str(product.get('color', '')).lower():
            score += 2.5

    for mat, kws in MATERIAL_KEYWORDS.items():
        if any(kw in query_lower for kw in kws) and mat in str(product.get('material', '')).lower():
            score += 2.5

    score += float(product.get('trending_score', 0)) * 1.5
    score += float(product.get('rating', 0)) * 1.0

    try:
        raw_price = str(product.get('price', '0')).replace('$', '').replace('€', '').replace(',', '').replace('pkr', '')
        product_price = float(raw_price)

        if price_range:
            if 'min' in price_range and product_price >= price_range['min']:
                score += 2.0
            if 'max' in price_range and product_price <= price_range['max']:
                score += 2.0

        if any(kw in query_lower for kw in INTENT_KEYWORDS["low_price"]) and product_price < 50:
            score += 1.5
        elif any(kw in query_lower for kw in INTENT_KEYWORDS["high_price"]) and product_price >= 150:
            score += 1.5

    except:
        pass

    if any(kw in query_lower for kw in INTENT_KEYWORDS["discount"]):
        score += 1.0

    return score

def filter_products(query: str, products: List[Dict[str, Any]]):
    query_lower = query.lower()
    filtered = list(products)
    desc_list = []

    price_range = parse_price_range(query)

    for category, kws in CATEGORY_KEYWORDS.items():
        if any(kw in query_lower for kw in kws):
            filtered = [
                p for p in filtered
                if category in p.get('category', '').lower() or category in p.get('title', '').lower()
            ]
            desc_list.append(category)
            break

    for color, kws in COLOR_KEYWORDS.items():
        if any(kw in query_lower for kw in kws):
            temp = [
                p for p in filtered
                if color in p.get('color', '').lower() or color in p.get('title', '').lower()
            ]
            if temp:
                filtered = temp
                desc_list.append(color)
                break

    if price_range:
        def check_price(p):
            try:
                p_str = str(p.get('price', '0')).replace('$', '').replace('€', '').replace(',', '').replace('pkr', '')
                val = float(p_str)
                if 'min' in price_range and val < price_range['min']:
                    return False
                if 'max' in price_range and val > price_range['max']:
                    return False
                return True
            except:
                return False

        filtered = [p for p in filtered if check_price(p)]
        desc_list.append("matching price criteria")

    scored = [{"product": p, "score": score_product_relevance(query, p, price_range)} for p in filtered]
    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    final = [x["product"] for x in ranked if x["score"] > 0.0]

    desc = " and ".join(desc_list) if desc_list else "your request"
    return final, desc

def get_faq_response(query: str) -> Optional[Dict[str, str]]:
    faq = BOT_DATA.get("faq", {})
    q = query.lower()

    if any(k in q for k in ["ship", "deliver", "ارسال", "versand", "delivery", "kab ayega"]):
        return faq.get("shipping")

    if any(k in q for k in ["return", "refund", "واپسی", "rückgabe", "exchange", "back"]):
        return faq.get("return")

    if any(k in q for k in ["track", "order", "ٹریک", "verfolgen", "status", "kahan hai"]):
        return faq.get("track")

    if any(k in q for k in ["why", "choose", "کیوں"]):
        return faq.get("Why I Choose Your Products")

    if any(k in q for k in ["best quality", "qualities", "business quality"]):
        return faq.get("What's the Best Quality of Your Business")
    
    if any(k in q for k in ["How", "Hello", "How are you", "What's going on"]): 
        return faq.get("Hello")

    return None

def get_dynamic_suggestions(user_id: str, context: str, lang: str) -> List[str]:
    if user_id not in USER_SESSION_HISTORY:
        USER_SESSION_HISTORY[user_id] = {"shown": [], "lang": lang, "last_query": ""}

    sugs_dict = BOT_DATA.get("smart_suggestions", {})
    all_sugs = sugs_dict.get(context, {}).get(lang, [])

    if not all_sugs:
        all_sugs = sugs_dict.get("greeting", {}).get(lang, [])

    shown = USER_SESSION_HISTORY[user_id].get("shown", [])
    available = [s for s in all_sugs if s not in shown]

    if len(available) < 2 and all_sugs:
        USER_SESSION_HISTORY[user_id]["shown"] = []
        available = all_sugs

    selected = random.sample(available, min(4, len(available)))
    USER_SESSION_HISTORY[user_id]["shown"] = list(set(USER_SESSION_HISTORY[user_id]["shown"] + selected))

    return selected

def generate_bot_response(user_id: str, msg: str):
    load_data_realtime()

    lang = detect_language(msg)
    USER_SESSION_HISTORY.setdefault(user_id, {})
    USER_SESSION_HISTORY[user_id]["lang"] = lang

    # Track the message as a search or question
    if len(msg.split()) > 1:  # consider multi-word messages as search/questions
        track_search(msg)
        track_question(msg)

    response = {"reply": None, "carousel": None, "suggestions": []}
    query_lower = msg.lower()

    # Discount messages
    if any(kw in query_lower for kw in INTENT_KEYWORDS["discount"]):
        discount_msg = BOT_DATA.get("discount_message", {}).get(
            lang, BOT_DATA.get("discount_message", {}).get("en")
        )
        if discount_msg:
            response["reply"] = discount_msg

    # FAQ responses
    faq = get_faq_response(msg)
    if faq:
        response["reply"] = faq.get(lang, faq.get("en"))
        response["suggestions"] = get_dynamic_suggestions(user_id, "greeting", lang)
        return response

    # Product search
    last_query = USER_SESSION_HISTORY[user_id].get("last_query", "")
    combined_query = (last_query + " " + msg).strip() if len(msg.split()) < 3 and last_query else msg
    filtered, desc = filter_products(combined_query, PRODUCTS_DATA)
    USER_SESSION_HISTORY[user_id]["last_query"] = combined_query

    if filtered:
        response["carousel"] = filtered[:8]
        reply_templates = {
            "en": f"Sure — based on your search for *{desc}*, here are the most relevant picks.",
            "ur": f"بالکل — آپ کی تلاش *{desc}* کی بنیاد پر یہ بہترین آپشنز ہیں:",
            "de": f"Gerne — basierend auf Ihrer Suche nach *{desc}* finden Sie hier passende Empfehlungen."
        }
        response["reply"] = reply_templates.get(lang, reply_templates["en"])
        response["suggestions"] = get_dynamic_suggestions(user_id, "greeting", lang)
        return response

    response["reply"] = {
        "en": "I couldn't find the perfect match — want to try another color, size, or price range?",
        "ur": "مجھے ٹھیک چیز نہیں ملی — کیا آپ رنگ، سائز یا قیمت بدل کر دیکھیں گے؟",
        "de": "Ich habe nichts Passendes gefunden — möchten Sie eine andere Farbe, Größe oder Preisspanne versuchen?"
    }.get(lang, "Let's refine your search a bit.")
    response["suggestions"] = get_dynamic_suggestions(user_id, "greeting", lang)
    return response

@app.get("/")
async def root():
    load_data_realtime()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "templates", "chat.html")

    if os.path.exists(html_path):
        return FileResponse(html_path)

    return JSONResponse({"status": "active", "info": "Server running. WebSocket at /ws/chat"})

@app.get("/Dashboard")
async def root():
    load_data_realtime()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "templates", "index.html")

    if os.path.exists(html_path):
        return FileResponse(html_path)

    return JSONResponse({"status": "active", "info": "Server running. WebSocket at /ws/chat"})

# =================================================
# ------------- ADMIN PANEL PASSWORD ---------------
# =================================================

@app.post("/password")
async def password_root(
    request: Request,
    password: str = Form(...),
    user_name: str = Form(...)
):

    # Get credentials from environment
    expected_password = os.getenv("SECRET_PASSWORD")
    expected_user = os.getenv("USER_NAME")

    # Proper authentication check
    if password == expected_password and user_name == expected_user:

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "status": "success"
            }
        )

    else:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "status": "failed"
            }
        )
 
# ----------------------------------
 
@app.get("/api/data")
async def get_home_data():
    """
    Synchronizes MongoDB data and serves a clean JSON payload for the LuxeStore Dashboard.
    Handles BSON _id serialization and maps multilingual bot metadata.
    """
    try:
        # 1. Trigger the realtime sync for PRODUCTS_DATA and BOT_DATA
        load_data_realtime()

        # 2. Extract Smart Suggestions from the BOT_DATA (the 'config' document)
        # Your MongoDB shows: smart_suggestions: { en: [...], ur: [...], de: [...] }
        raw_suggestions = BOT_DATA.get("smart_suggestions", {})
        
        # 3. Clean and serialize the product data to ensure no BSON errors
        serialized_products = []
        for p in PRODUCTS_DATA:
            clean_p = {**p}
            if "_id" in clean_p:
                clean_p["_id"] = str(clean_p["_id"])
            serialized_products.append(clean_p)

        # 4. Construct the professional payload
        return {
            "products": serialized_products,
            "config": {
                "faq": BOT_DATA.get("faq", {}),
                "initial_message": BOT_DATA.get("initial_message", {}),
                "discount_message": BOT_DATA.get("discount_message", {}),
                "greeting": BOT_DATA.get("greeting", {}),
                "supported_languages": BOT_DATA.get("supported_languages", ["en", "ur"]),
                # Pass the full suggestions object so the UI can handle language switching
                "smart_suggestions": {
                    "en": raw_suggestions.get("en", []),
                    "ur": raw_suggestions.get("ur", []),
                    "de": raw_suggestions.get("de", [])
                }
            }
        }
    except Exception as e:
        logger.error(f"Dashboard Data API Error: {e}")
        return {
            "products": [],
            "config": {"faq": {}, "smart_suggestions": {"en": [], "ur": []}},
            "error": "Failed to synchronize with MongoDB Atlas"
        }
        
# WEBSOCKETS 
app.include_router(websocket_router)
        
# Initialize analytics
analytics.init_analytics(analytics_col)

# ===============================
# ADD NEW PRODUCT
# ===============================
@app.post("/Add_product")
async def add_new_product(
    request: Request,
    id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    color: str = Form(...),
    material: str = Form(...),
    price: float = Form(...),
    rating: float = Form(...),
    trending_score: float = Form(...),
    image: str = Form(...),
    image_link: str = Form(...)
):
    new_product = {
        "id": id,
        "title": title,
        "description": description,
        "category": category,
        "color": color,
        "material": material,
        "price": price,
        "rating": rating,
        "trending_score": trending_score,
        "image": image,
        "image_link": image_link
    }

    if products_col is None:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "message": "Database not connected"}
        )

    products_col.insert_one(new_product)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "message": "Product added successfully!"}
    )

# ===============================
# DELETE PRODUCT
# ===============================
@app.post("/delete_product")
async def delete_product(request: Request, id: str = Form(...)):
    try:
        result = products_col.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "message": "Product not found!"}
            )
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "message": "Product deleted successfully!"}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "message": f"Error deleting product: {str(e)}"}
        )

# ===============================
# UPDATE PRODUCT
# ===============================
@app.post("/update_product")
async def update_product(
    request: Request,
    product_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    color: str = Form(...),
    material: str = Form(...),
    price: float = Form(...),
    rating: float = Form(...),
    trending_score: float = Form(...),
    image: str = Form(...),
    image_link: str = Form(...)
):
    update_data = {
        "title": title,
        "description": description,
        "category": category,
        "color": color,
        "material": material,
        "price": price,
        "rating": rating,
        "trending_score": trending_score,
        "image": image,
        "image_link": image_link
    }

    if products_col is None:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "message": "Database not connected"}
        )

    result = products_col.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        message = "No product found with this ID."
    else:
        message = "Product updated successfully!"

    # Track price update in analytics
    analytics.track_price_update(analytics_col, product_id)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "message": message}
    )

# ===============================
# TRACK PRODUCT CLICK (API)
# ===============================
@app.post("/track_click")
async def track_click_api(product_id: str = Form(...)):
    analytics.track_click(analytics_col, product_id)
    return {"status": "tracked"}

# ===============================
# TRACK SEARCH (CALL IN YOUR SEARCH LOGIC)
# ===============================
def track_search(query: str):
    analytics.track_search(analytics_col, query)

# ===============================
# TRACK QUESTION (CALL IN YOUR CHATBOT LOGIC)
# ===============================
def track_question(question: str):
    analytics.track_question(analytics_col, question)

# ===============================
# TRACK LANGUAGE (API)
# ===============================
@app.post("/track_language")
async def track_language_api(language: str = Form(...)):
    analytics.track_language(analytics_col, language)
    return {"status": "tracked", "language": language}

# ===============================
# GET ANALYTICS (API)
# ===============================
@app.get("/api/analytics")
async def get_analytics():
    data = analytics.get_analytics_data(analytics_col)
    return JSONResponse(data)

# ===============================
# DASHBOARD PAGE
# ===============================
@app.get("/analytics_dashboard", response_class=HTMLResponse)
async def analytics_dashboard(request: Request):
    """
    Returns the HTML page for the analytics dashboard.
    The page fetches /api/analytics dynamically for charts.
    """
    return templates.TemplateResponse("index.html", {"request": request})
