# keywords.py
from langdetect import detect

# --- LANGUAGE DETECTION ---
def detect_language(text: str) -> str:
    try:
        if not text or not text.strip():
            return "en"
        # Urdu/Arabic character range check
        if any("\u0600" <= c <= "\u06FF" for c in text):
            return "ur"
        
        lang = detect(text)
        if lang.startswith("ur"): return "ur"
        if lang.startswith("de"): return "de"
        return "en"
    except Exception:
        return "en"

# --- SMART MATCHING DATA ---
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
    "synthetic": ["nylon", "polyester", "نایلان", "پالئیےستر", "spandex", "rayon", "chiffon"],
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
