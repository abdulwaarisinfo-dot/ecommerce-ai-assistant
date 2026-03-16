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

# from analytics import router as analytics_router
# from analytics import init_analytics, track_search, track_question, track_price_update

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

def detect_language(text: str) -> str:
    try:
        if not text or not text.strip():
            return "en"

        if any("\u0600" <= c <= "\u06FF" for c in text):
            return "ur"

        lang = detect(text)

        if lang.startswith("ur"):
            return "ur"
        if lang.startswith("de"):
            return "de"

        return "en"
    except Exception:
        return "en"
    
# ============================================================
# ---------------- SMART MATCHING DATABASE -------------------
# ============================================================

COLOR_KEYWORDS = {
    "black": ["black", "کالا", "سیاہ", "dark", "schwarz", "kala", "onyx"],
    "blue": ["blue", "نیلا", "blau", "navy", "neela", "azure", "indigo", "light blue"],
    "white": ["white", "سفید", "weiß", "safed", "ivory", "cream", "snow"],
    "red": ["red", "لال", "rot", "surkh", "crimson", "scarlet"],
    "green": ["green", "سبز", "grün", "sabz", "olive", "sage", "teal"],
    "grey": ["grey", "گرے", "grau", "gray", "silver", "charcoal"],
    "khaki": ["khaki", "beige", "خاکی", "بادامی", "tan", "sand"],
    "yellow": ["yellow", "پیلا", "gelb", "neon", "gold"]
}

MATERIAL_KEYWORDS = {
    "leather": ["leather", "چمڑا", "leder", "genuine leather"],
    "cotton": ["cotton", "کاٹن", "سوتی", "baumwolle", "twill", "organic cotton"],
    "denim": ["denim", "ڈينم", "jeans", "rigid denim"],
    "wool": ["wool", "اون", "اونی", "wolle", "merino", "lambswool", "knit"],
    "silk": ["silk", "ریشم", "سلک", "seide", "mulberry silk", "satin"],
    "linen": ["linen", "لینن", "leinen", "linen blend"],
    "synthetic": ["nylon", "polyester", "نایلان", "پالئیےسٹر", "spandex", "rayon", "chiffon"],
    "fleece": ["fleece", "فلِیس", "brushed cotton"]
}

CATEGORY_KEYWORDS = {
    "jacket": ["jacket", "جیکٹ", "jacken", "coat", "blazer", "outerwear", "trucker", "windbreaker"],
    "shirt": ["shirt", "شرٹ", "hemd", "tshirt", "tee", "top", "camisole", "button-down", "flannel"],
    "pants": ["pant", "pants", "پینٹ", "hosen", "jeans", "trousers", "leggings", "chinos", "shorts"],
    "dress": ["dress", "ڈریس", "kleid", "mini dress", "maxi", "lbd", "gown"],
    "hoodie_sweater": ["hoodie", "ہوڈی", "sweater", "سویٹر", "kapuzenpullover", "knitwear", "pullover", "jerzi"],
    "skirt": ["skirt", "اسکرٹ", "pleated skirt", "rock"],
    "shoes": ["sneakers"]
}

INTENT_KEYWORDS = {
    "discount": ["discount", "sale", "deal", "offer", "cheap", "سستا", "رعایت", "rabatt", "clearance"],
    "high_quality": ["best", "premium", "top", "excellent", "بہترین", "اعلی", "luxury", "expensive"],
    "style": ["trendy", "vintage", "casual", "formal", "fashion", "اسٹائل"],
    "weather": ["winter", "summer", "cold", "warm", "سردی", "گرمی"],
    "low_price": ["cheap", "budget", "low price", "affordable", "سستا"],
    "high_price": ["premium", "expensive", "high price", "luxury"]
}

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
    
# =============================
# --------- WEB SOCKETS --------
# ==============================

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = str(id(websocket))

    load_data_realtime()

    lang = "en"
    initial_message = BOT_DATA.get("initial_message", {}).get(lang, "Hello! How can I help?")

    await websocket.send_json({
        "reply": initial_message,
        "carousel": None,
        "suggestions": get_dynamic_suggestions(user_id, "greeting", lang)
    })

    try:
        while True:
            msg = await websocket.receive_text()


            bot = generate_bot_response(user_id, msg)

            await asyncio.sleep(0.2)

            await websocket.send_json(bot)

    except WebSocketDisconnect:
        logging.info(f"User disconnected: {user_id}")

    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass
        
# ========================================
# -------- ADD NEW PRODUCTS DATA ---------
# ========================================

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

    # Check DB connection
    if products_col is None:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "message": "Database not connected"}
        )

    # Insert product
    products_col.insert_one(new_product)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "message": "Product added successfully!"}
    )

# ==========================================
# ---------- DELETE PRODUCTS DATA -----------
# =============================================

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
        
# ========================================
# -------- UPDATE PRODUCTS DATA ----------
# ========================================  

@app.post("/update_product")
async def update_product(
    request: Request,
    product_id: str = Form(...),  # Unique product ID
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

    # Prepare update data
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

    # Check DB connection
    if products_col is None:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "message": "Database not connected"}
        )

    # Perform the update
    result = products_col.update_one(
        {"_id": ObjectId(product_id)},  # Filter by product ID
        {"$set": update_data}           # Set the new values
    )

    if result.matched_count == 0:
        message = "No product found with this ID."
    else:
        message = "Product updated successfully!"

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "message": message}
    )

# ===============================
# INIT ANALYTICS
# ===============================
def init_analytics():
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

init_analytics()

# ===============================
# TRACK SEARCH
# ===============================
def track_search(query: str):
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {"total_searches": 1, f"product_search.{query.lower()}": 1}}
    )

# ===============================
# TRACK QUESTION
# ===============================
def track_question(question: str):
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {f"most_questions.{question}": 1}}
    )

# ===============================
# TRACK PRODUCT CLICK
# ===============================
@app.post("/track_click")
async def track_click(product_id: str = Form(...)):
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {"total_clicks": 1, f"product_clicks.{product_id}": 1}}
    )
    return {"status": "tracked"}

# ===============================
# TRACK PRICE UPDATE
# ===============================
def track_price_update(product_id: str):
    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {f"price_updates.{product_id}": 1}}
    )

# ===============================
# GET ANALYTICS DATA (JSON)
# ===============================
@app.get("/api/analytics")
async def get_analytics():
    data = analytics_col.find_one({"type": "analytics"})
    if "_id" in data:
        data["_id"] = str(data["_id"])
    return data

# ======= TRACK LANGUAGES =========
#  ---------------------------------
#  ==================================

# ===============================
# TRACK LANGUAGE
# ===============================
@app.post("/track_language")
async def track_language(language: str = Form(...)):
    """
    Tracks which language users are using in the chatbot.
    Example: en, ur, hi, ar
    """

    analytics_col.update_one(
        {"type": "analytics"},
        {"$inc": {f"supported_languages.{language.lower()}": 1}}
    )

    return {"status": "tracked", "language": language}

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
