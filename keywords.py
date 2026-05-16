# keywords.py
# ============================================================
# LANGUAGE DETECTION & SMART KEYWORD MATCHING
# ============================================================

from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0  # Consistent language detection across runs


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(text: str) -> str:
    """
    Detects the language of the input text.
    Supports: English (en), Urdu (ur), German (de).
    Falls back to English on failure or short input.
    """
    try:
        if not text or not text.strip():
            return "en"

        # Fast-path: Urdu/Arabic Unicode block check
        urdu_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        if urdu_chars > len(text) * 0.1:  # >10% Urdu characters
            return "ur"

        detected = detect(text)

        if detected.startswith("ur"):
            return "ur"
        if detected.startswith("de"):
            return "de"
        return "en"

    except Exception:
        return "en"


# ============================================================
# COLOR KEYWORDS
# ============================================================

COLOR_KEYWORDS = {
    "black": [
        "black", "کالا", "سیاہ", "dark", "schwarz", "kala",
        "onyx", "jet black", "charcoal black"
    ],
    "blue": [
        "blue", "نیلا", "blau", "navy", "neela", "azure",
        "indigo", "light blue", "cobalt", "royal blue", "sky blue"
    ],
    "white": [
        "white", "سفید", "weiß", "safed", "ivory", "cream",
        "snow", "off white", "pearl"
    ],
    "red": [
        "red", "لال", "rot", "surkh", "crimson",
        "scarlet", "ruby", "maroon"
    ],
    "green": [
        "green", "سبز", "grün", "sabz", "olive",
        "sage", "teal", "emerald", "forest green", "mint"
    ],
    "grey": [
        "grey", "گرے", "grau", "gray", "silver",
        "charcoal", "ash", "slate"
    ],
    "khaki": [
        "khaki", "beige", "خاکی", "بادامی", "tan",
        "sand", "camel", "nude", "taupe"
    ],
    "yellow": [
        "yellow", "پیلا", "gelb", "neon yellow", "gold",
        "mustard", "amber", "lemon"
    ],
    "brown": [
        "brown", "بھورا", "braun", "chocolate", "coffee",
        "mahogany", "walnut", "rust"
    ],
    "pink": [
        "pink", "گلابی", "rosa", "blush", "rose",
        "coral", "salmon", "fuchsia"
    ],
    "purple": [
        "purple", "جامنی", "lila", "violet", "lavender",
        "plum", "mauve", "grape"
    ],
    "orange": [
        "orange", "نارنجی", "narnji", "peach",
        "apricot", "terracotta", "burnt orange"
    ],
    "burgundy": [
        "burgundy", "wine", "maroon", "oxblood",
        "deep red", "claret"
    ],
}


# ============================================================
# MATERIAL KEYWORDS
# ============================================================

MATERIAL_KEYWORDS = {
    "leather": [
        "leather", "چمڑا", "leder", "genuine leather",
        "faux leather", "vegan leather", "pu leather", "suede"
    ],
    "cotton": [
        "cotton", "کاٹن", "سوتی", "baumwolle", "twill",
        "organic cotton", "pima cotton", "percale", "poplin",
        "oxford cloth", "chambray"
    ],
    "denim": [
        "denim", "ڈینم", "jeans", "rigid denim",
        "stretch denim", "raw denim", "chambray denim"
    ],
    "wool": [
        "wool", "اون", "اونی", "wolle", "merino",
        "lambswool", "knit", "knitwear", "cashmere",
        "camel wool", "herringbone"
    ],
    "silk": [
        "silk", "ریشم", "سلک", "seide", "mulberry silk",
        "satin", "charmeuse", "crepe silk"
    ],
    "linen": [
        "linen", "لینن", "leinen", "linen blend",
        "ramie", "breathable fabric"
    ],
    "synthetic": [
        "nylon", "polyester", "نایلان", "پالئیسٹر",
        "spandex", "rayon", "chiffon", "viscose",
        "modal", "acetate", "microfiber"
    ],
    "fleece": [
        "fleece", "فلیس", "brushed cotton",
        "sherpa", "polar fleece", "teddy fleece"
    ],
    "velvet": [
        "velvet", "مخمل", "samt", "crushed velvet",
        "velour", "velveteen"
    ],
}


# ============================================================
# CATEGORY KEYWORDS
# ============================================================

CATEGORY_KEYWORDS = {
    "jacket": [
        "jacket", "جیکٹ", "jacken", "coat", "blazer",
        "outerwear", "trucker jacket", "windbreaker", "trench coat",
        "puffer jacket", "bomber jacket", "biker jacket", "peacoat",
        "raincoat", "overcoat", "varsity jacket", "leather jacket"
    ],
    "shirt": [
        "shirt", "شرٹ", "hemd", "t-shirt", "tshirt", "tee",
        "top", "camisole", "button-down", "flannel shirt",
        "polo shirt", "henley", "halter top", "blouse",
        "crop top", "vest", "tank top", "tube top"
    ],
    "pants": [
        "pant", "pants", "پینٹ", "hosen", "jeans", "trousers",
        "leggings", "chinos", "shorts", "joggers", "cargo pants",
        "wide leg", "slim fit", "straight leg", "palazzo",
        "culottes", "capri", "slacks", "skinny jeans", "bootcut"
    ],
    "dress": [
        "dress", "ڈریس", "kleid", "mini dress", "maxi dress",
        "lbd", "gown", "slip dress", "wrap dress", "midi dress",
        "sundress", "bodycon dress", "floral dress", "formal dress",
        "casual dress", "party dress", "evening gown"
    ],
    "hoodie_sweater": [
        "hoodie", "ہوڈی", "sweater", "سویٹر",
        "kapuzenpullover", "knitwear", "pullover", "jumper",
        "crewneck", "zip hoodie", "oversized hoodie", "sweatshirt",
        "cardigan", "turtleneck", "cable knit", "jerzi"
    ],
    "skirt": [
        "skirt", "اسکرٹ", "pleated skirt", "rock",
        "mini skirt", "midi skirt", "maxi skirt", "a-line skirt",
        "pencil skirt", "wrap skirt", "tiered skirt"
    ],
    "shoes": [
        "shoes", "sneakers", "جوتے", "schuhe",
        "boots", "loafers", "heels", "sandals",
        "trainers", "running shoes", "formal shoes",
        "ankle boots", "chelsea boots", "mules", "platforms"
    ],
    "accessories": [
        "belt", "scarf", "hat", "cap", "bag",
        "purse", "wallet", "sunglasses", "watch",
        "jewellery", "necklace", "bracelet", "earrings"
    ],
}


# ============================================================
# INTENT KEYWORDS
# ============================================================

INTENT_KEYWORDS = {
    "discount": [
        "discount", "sale", "deal", "offer", "cheap", "سستا",
        "رعایت", "rabatt", "clearance", "promo", "coupon",
        "off", "reduced", "markdown", "best price"
    ],
    "high_quality": [
        "best", "premium", "top", "excellent", "بہترین",
        "اعلی", "luxury", "expensive", "high quality", "designer",
        "finest", "superior"
    ],
    "style": [
        "trendy", "vintage", "casual", "formal", "fashion",
        "اسٹائل", "chic", "classic", "elegant", "streetwear",
        "boho", "minimalist", "sporty", "preppy"
    ],
    "weather": [
        "winter", "summer", "cold", "warm", "سردی", "گرمی",
        "autumn", "fall", "spring", "rain", "snow",
        "monsoon", "hot", "freezing"
    ],
    "low_price": [
        "cheap", "budget", "low price", "affordable", "سستا",
        "economical", "inexpensive", "value", "under", "below"
    ],
    "high_price": [
        "premium", "expensive", "high price", "luxury",
        "top tier", "high end", "above", "over"
    ],
    "new_arrivals": [
        "new", "latest", "fresh", "just in", "new arrivals",
        "نیا", "recently added", "trending now"
    ],
    "gift": [
        "gift", "present", "تحفہ", "geschenk",
        "for her", "for him", "birthday", "anniversary", "surprise"
    ],
    "occasion": [
        "office", "work", "party", "wedding", "date",
        "casual", "formal", "gym", "workout", "beach",
        "travel", "outdoor", "college", "school"
    ],
}
