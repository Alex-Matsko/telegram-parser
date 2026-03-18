"""
Comprehensive synonym dictionaries for Apple products.
Used by the regex parser and normalizer to resolve abbreviations,
aliases, and variations in price messages.
"""

# --------------------------------------------------------------------------
# MODEL ALIASES  →  (line, model, category)
# --------------------------------------------------------------------------
MODEL_ALIASES: dict[str, tuple[str, str, str]] = {
    # iPhone 16 family
    "iphone 16 pro max": ("iPhone", "iPhone 16 Pro Max", "smartphone"),
    "16 pro max": ("iPhone", "iPhone 16 Pro Max", "smartphone"),
    "16pm": ("iPhone", "iPhone 16 Pro Max", "smartphone"),
    "16 pm": ("iPhone", "iPhone 16 Pro Max", "smartphone"),
    "16promax": ("iPhone", "iPhone 16 Pro Max", "smartphone"),
    "16 promax": ("iPhone", "iPhone 16 Pro Max", "smartphone"),
    "iphone 16 pro": ("iPhone", "iPhone 16 Pro", "smartphone"),
    "16 pro": ("iPhone", "iPhone 16 Pro", "smartphone"),
    "16p": ("iPhone", "iPhone 16 Pro", "smartphone"),
    "16 p": ("iPhone", "iPhone 16 Pro", "smartphone"),
    "iphone 16 plus": ("iPhone", "iPhone 16 Plus", "smartphone"),
    "16 plus": ("iPhone", "iPhone 16 Plus", "smartphone"),
    "16+": ("iPhone", "iPhone 16 Plus", "smartphone"),
    "iphone 16": ("iPhone", "iPhone 16", "smartphone"),
    "iphone16": ("iPhone", "iPhone 16", "smartphone"),

    # iPhone 15 family
    "iphone 15 pro max": ("iPhone", "iPhone 15 Pro Max", "smartphone"),
    "15 pro max": ("iPhone", "iPhone 15 Pro Max", "smartphone"),
    "15pm": ("iPhone", "iPhone 15 Pro Max", "smartphone"),
    "15 pm": ("iPhone", "iPhone 15 Pro Max", "smartphone"),
    "15promax": ("iPhone", "iPhone 15 Pro Max", "smartphone"),
    "15 promax": ("iPhone", "iPhone 15 Pro Max", "smartphone"),
    "iphone 15 pro": ("iPhone", "iPhone 15 Pro", "smartphone"),
    "15 pro": ("iPhone", "iPhone 15 Pro", "smartphone"),
    "15p": ("iPhone", "iPhone 15 Pro", "smartphone"),
    "15 p": ("iPhone", "iPhone 15 Pro", "smartphone"),
    "iphone 15 plus": ("iPhone", "iPhone 15 Plus", "smartphone"),
    "15 plus": ("iPhone", "iPhone 15 Plus", "smartphone"),
    "15+": ("iPhone", "iPhone 15 Plus", "smartphone"),
    "iphone 15": ("iPhone", "iPhone 15", "smartphone"),
    "iphone15": ("iPhone", "iPhone 15", "smartphone"),

    # iPhone 14 family
    "iphone 14 pro max": ("iPhone", "iPhone 14 Pro Max", "smartphone"),
    "14 pro max": ("iPhone", "iPhone 14 Pro Max", "smartphone"),
    "14pm": ("iPhone", "iPhone 14 Pro Max", "smartphone"),
    "14 pm": ("iPhone", "iPhone 14 Pro Max", "smartphone"),
    "14promax": ("iPhone", "iPhone 14 Pro Max", "smartphone"),
    "14 promax": ("iPhone", "iPhone 14 Pro Max", "smartphone"),
    "iphone 14 pro": ("iPhone", "iPhone 14 Pro", "smartphone"),
    "14 pro": ("iPhone", "iPhone 14 Pro", "smartphone"),
    "14p": ("iPhone", "iPhone 14 Pro", "smartphone"),
    "14 p": ("iPhone", "iPhone 14 Pro", "smartphone"),
    "iphone 14 plus": ("iPhone", "iPhone 14 Plus", "smartphone"),
    "14 plus": ("iPhone", "iPhone 14 Plus", "smartphone"),
    "14+": ("iPhone", "iPhone 14 Plus", "smartphone"),
    "iphone 14": ("iPhone", "iPhone 14", "smartphone"),
    "iphone14": ("iPhone", "iPhone 14", "smartphone"),

    # iPhone 13 family
    "iphone 13 pro max": ("iPhone", "iPhone 13 Pro Max", "smartphone"),
    "13 pro max": ("iPhone", "iPhone 13 Pro Max", "smartphone"),
    "13pm": ("iPhone", "iPhone 13 Pro Max", "smartphone"),
    "13 pm": ("iPhone", "iPhone 13 Pro Max", "smartphone"),
    "13promax": ("iPhone", "iPhone 13 Pro Max", "smartphone"),
    "iphone 13 pro": ("iPhone", "iPhone 13 Pro", "smartphone"),
    "13 pro": ("iPhone", "iPhone 13 Pro", "smartphone"),
    "13p": ("iPhone", "iPhone 13 Pro", "smartphone"),
    "iphone 13 mini": ("iPhone", "iPhone 13 Mini", "smartphone"),
    "13 mini": ("iPhone", "iPhone 13 Mini", "smartphone"),
    "iphone 13": ("iPhone", "iPhone 13", "smartphone"),
    "iphone13": ("iPhone", "iPhone 13", "smartphone"),

    # iPhone 12 family
    "iphone 12 pro max": ("iPhone", "iPhone 12 Pro Max", "smartphone"),
    "12 pro max": ("iPhone", "iPhone 12 Pro Max", "smartphone"),
    "12pm": ("iPhone", "iPhone 12 Pro Max", "smartphone"),
    "12 pm": ("iPhone", "iPhone 12 Pro Max", "smartphone"),
    "12promax": ("iPhone", "iPhone 12 Pro Max", "smartphone"),
    "iphone 12 pro": ("iPhone", "iPhone 12 Pro", "smartphone"),
    "12 pro": ("iPhone", "iPhone 12 Pro", "smartphone"),
    "12p": ("iPhone", "iPhone 12 Pro", "smartphone"),
    "iphone 12 mini": ("iPhone", "iPhone 12 Mini", "smartphone"),
    "12 mini": ("iPhone", "iPhone 12 Mini", "smartphone"),
    "iphone 12": ("iPhone", "iPhone 12", "smartphone"),
    "iphone12": ("iPhone", "iPhone 12", "smartphone"),

    # iPhone SE
    "iphone se 3": ("iPhone", "iPhone SE 3", "smartphone"),
    "iphone se 2022": ("iPhone", "iPhone SE 3", "smartphone"),
    "se 3": ("iPhone", "iPhone SE 3", "smartphone"),
    "iphone se 2": ("iPhone", "iPhone SE 2", "smartphone"),
    "iphone se 2020": ("iPhone", "iPhone SE 2", "smartphone"),
    "se 2": ("iPhone", "iPhone SE 2", "smartphone"),
    "iphone se": ("iPhone", "iPhone SE 3", "smartphone"),

    # AirPods
    "airpods pro 2 usb-c": ("AirPods", "AirPods Pro 2 USB-C", "headphones"),
    "airpods pro 2 usb c": ("AirPods", "AirPods Pro 2 USB-C", "headphones"),
    "airpods pro 2 type-c": ("AirPods", "AirPods Pro 2 USB-C", "headphones"),
    "airpods pro 2 type c": ("AirPods", "AirPods Pro 2 USB-C", "headphones"),
    "airpods pro 2": ("AirPods", "AirPods Pro 2", "headphones"),
    "airpods pro2": ("AirPods", "AirPods Pro 2", "headphones"),
    "app2": ("AirPods", "AirPods Pro 2", "headphones"),
    "airpods pro": ("AirPods", "AirPods Pro 2", "headphones"),
    "airpods 4 anc": ("AirPods", "AirPods 4 ANC", "headphones"),
    "airpods 4": ("AirPods", "AirPods 4", "headphones"),
    "airpods 3": ("AirPods", "AirPods 3", "headphones"),
    "airpods 2": ("AirPods", "AirPods 2", "headphones"),
    "airpods": ("AirPods", "AirPods 3", "headphones"),
    "airpods max 2": ("AirPods", "AirPods Max 2", "headphones"),
    "airpods max": ("AirPods", "AirPods Max", "headphones"),

    # Apple Watch
    "apple watch ultra 2": ("Apple Watch", "Apple Watch Ultra 2", "watch"),
    "aw ultra 2": ("Apple Watch", "Apple Watch Ultra 2", "watch"),
    "watch ultra 2": ("Apple Watch", "Apple Watch Ultra 2", "watch"),
    "awu2": ("Apple Watch", "Apple Watch Ultra 2", "watch"),
    "apple watch ultra": ("Apple Watch", "Apple Watch Ultra", "watch"),
    "aw ultra": ("Apple Watch", "Apple Watch Ultra", "watch"),
    "watch ultra": ("Apple Watch", "Apple Watch Ultra", "watch"),
    "apple watch series 10": ("Apple Watch", "Apple Watch Series 10", "watch"),
    "apple watch s10": ("Apple Watch", "Apple Watch Series 10", "watch"),
    "aw s10": ("Apple Watch", "Apple Watch Series 10", "watch"),
    "aws10": ("Apple Watch", "Apple Watch Series 10", "watch"),
    "watch 10": ("Apple Watch", "Apple Watch Series 10", "watch"),
    "apple watch series 9": ("Apple Watch", "Apple Watch Series 9", "watch"),
    "apple watch s9": ("Apple Watch", "Apple Watch Series 9", "watch"),
    "aw s9": ("Apple Watch", "Apple Watch Series 9", "watch"),
    "aws9": ("Apple Watch", "Apple Watch Series 9", "watch"),
    "watch 9": ("Apple Watch", "Apple Watch Series 9", "watch"),
    "apple watch se 2": ("Apple Watch", "Apple Watch SE 2", "watch"),
    "aw se 2": ("Apple Watch", "Apple Watch SE 2", "watch"),
    "apple watch se": ("Apple Watch", "Apple Watch SE 2", "watch"),
    "aw se": ("Apple Watch", "Apple Watch SE 2", "watch"),

    # MacBook
    "macbook pro 16": ("MacBook", "MacBook Pro 16", "laptop"),
    "mbp 16": ("MacBook", "MacBook Pro 16", "laptop"),
    "macbook pro 14": ("MacBook", "MacBook Pro 14", "laptop"),
    "mbp 14": ("MacBook", "MacBook Pro 14", "laptop"),
    "macbook pro 13": ("MacBook", "MacBook Pro 13", "laptop"),
    "mbp 13": ("MacBook", "MacBook Pro 13", "laptop"),
    "macbook pro": ("MacBook", "MacBook Pro", "laptop"),
    "mbp": ("MacBook", "MacBook Pro", "laptop"),
    "macbook air 15": ("MacBook", "MacBook Air 15", "laptop"),
    "mba 15": ("MacBook", "MacBook Air 15", "laptop"),
    "macbook air 13": ("MacBook", "MacBook Air 13", "laptop"),
    "mba 13": ("MacBook", "MacBook Air 13", "laptop"),
    "macbook air": ("MacBook", "MacBook Air", "laptop"),
    "mba": ("MacBook", "MacBook Air", "laptop"),

    # iPad
    "ipad pro 13": ("iPad", "iPad Pro 13", "tablet"),
    "ipad pro 12.9": ("iPad", "iPad Pro 13", "tablet"),
    "ipad pro 11": ("iPad", "iPad Pro 11", "tablet"),
    "ipad pro": ("iPad", "iPad Pro", "tablet"),
    "ipad air 13": ("iPad", "iPad Air 13", "tablet"),
    "ipad air 11": ("iPad", "iPad Air 11", "tablet"),
    "ipad air": ("iPad", "iPad Air", "tablet"),
    "ipad mini 7": ("iPad", "iPad Mini 7", "tablet"),
    "ipad mini": ("iPad", "iPad Mini", "tablet"),
    "ipad 10": ("iPad", "iPad 10", "tablet"),
    "ipad": ("iPad", "iPad", "tablet"),

    # Mac Mini / Mac Studio
    "mac mini m4 pro": ("Mac", "Mac Mini M4 Pro", "desktop"),
    "mac mini m4": ("Mac", "Mac Mini M4", "desktop"),
    "mac mini": ("Mac", "Mac Mini", "desktop"),
    "mac studio m4 max": ("Mac", "Mac Studio M4 Max", "desktop"),
    "mac studio m4 ultra": ("Mac", "Mac Studio M4 Ultra", "desktop"),
    "mac studio": ("Mac", "Mac Studio", "desktop"),
}

# --------------------------------------------------------------------------
# COLOR ALIASES  →  canonical color name
# --------------------------------------------------------------------------
COLOR_ALIASES: dict[str, str] = {
    # iPhone 15 Pro colors
    "nat": "Natural Titanium",
    "natural": "Natural Titanium",
    "natural titanium": "Natural Titanium",
    "натуральный": "Natural Titanium",
    "натуральный титан": "Natural Titanium",
    "bt": "Blue Titanium",
    "blue titanium": "Blue Titanium",
    "blue titan": "Blue Titanium",
    "голубой титан": "Blue Titanium",
    "синий титан": "Blue Titanium",
    "wt": "White Titanium",
    "white titanium": "White Titanium",
    "белый титан": "White Titanium",
    "bkt": "Black Titanium",
    "black titanium": "Black Titanium",
    "черный титан": "Black Titanium",

    # iPhone 16 Pro colors
    "desert": "Desert Titanium",
    "desert titanium": "Desert Titanium",
    "dt": "Desert Titanium",

    # Standard iPhone colors
    "black": "Black",
    "blk": "Black",
    "bk": "Black",
    "черный": "Black",
    "чёрный": "Black",
    "white": "White",
    "wh": "White",
    "белый": "White",
    "blue": "Blue",
    "bl": "Blue",
    "синий": "Blue",
    "голубой": "Blue",
    "red": "Red",
    "product red": "Red",
    "(product) red": "Red",
    "красный": "Red",
    "green": "Green",
    "gr": "Green",
    "зеленый": "Green",
    "зелёный": "Green",
    "yellow": "Yellow",
    "yl": "Yellow",
    "желтый": "Yellow",
    "жёлтый": "Yellow",
    "pink": "Pink",
    "pk": "Pink",
    "розовый": "Pink",
    "purple": "Purple",
    "pr": "Purple",
    "фиолетовый": "Purple",
    "starlight": "Starlight",
    "sl": "Starlight",
    "сияющая звезда": "Starlight",
    "midnight": "Midnight",
    "mn": "Midnight",
    "темная ночь": "Midnight",
    "silver": "Silver",
    "sv": "Silver",
    "серебристый": "Silver",
    "gold": "Gold",
    "gd": "Gold",
    "золотой": "Gold",
    "space black": "Space Black",
    "sb": "Space Black",
    "space gray": "Space Gray",
    "sg": "Space Gray",
    "серый космос": "Space Gray",

    # iPhone 16 new colors
    "ultramarine": "Ultramarine",
    "teal": "Teal",

    # AirPods Max colors
    "sky blue": "Sky Blue",
    "orange": "Orange",
    "оранжевый": "Orange",
    "midnight blue": "Midnight Blue",
}

# --------------------------------------------------------------------------
# MEMORY ALIASES  →  canonical memory string
# --------------------------------------------------------------------------
MEMORY_ALIASES: dict[str, str] = {
    "32": "32GB",
    "32gb": "32GB",
    "64": "64GB",
    "64gb": "64GB",
    "128": "128GB",
    "128gb": "128GB",
    "256": "256GB",
    "256gb": "256GB",
    "512": "512GB",
    "512gb": "512GB",
    "1tb": "1TB",
    "1 tb": "1TB",
    "1024": "1TB",
    "1024gb": "1TB",
    "2tb": "2TB",
    "2 tb": "2TB",

    # MacBook RAM
    "8gb ram": "8GB",
    "16gb ram": "16GB",
    "18gb ram": "18GB",
    "24gb ram": "24GB",
    "32gb ram": "32GB",
    "36gb ram": "36GB",
    "48gb ram": "48GB",
    "64gb ram": "64GB",
    "96gb ram": "96GB",
    "128gb ram": "128GB",
    "192gb ram": "192GB",
}

# --------------------------------------------------------------------------
# CONDITION ALIASES  →  canonical condition
# --------------------------------------------------------------------------
CONDITION_ALIASES: dict[str, str] = {
    "new": "new",
    "новый": "new",
    "нов": "new",
    "sealed": "new",
    "запечатан": "new",
    "used": "used",
    "б/у": "used",
    "бу": "used",
    "bu": "used",
    "ref": "refurbished",
    "refurbished": "refurbished",
    "refurb": "refurbished",
    "восстановленный": "refurbished",
    "cpo": "refurbished",
    "like new": "used",
    "как новый": "used",
    "идеал": "used",
}

# --------------------------------------------------------------------------
# SIM TYPE ALIASES
# --------------------------------------------------------------------------
SIM_TYPE_ALIASES: dict[str, str] = {
    "esim": "esim",
    "e-sim": "esim",
    "dual": "dual",
    "dual sim": "dual",
    "2sim": "dual",
    "2 sim": "dual",
    "nano": "dual",
    "physical": "dual",
    "phy": "dual",
    "фыз": "dual",
    "физ": "dual",
}

# --------------------------------------------------------------------------
# CURRENCY ALIASES
# --------------------------------------------------------------------------
CURRENCY_ALIASES: dict[str, str] = {
    "$": "USD",
    "usd": "USD",
    "долл": "USD",
    "руб": "RUB",
    "₽": "RUB",
    "rub": "RUB",
    "р": "RUB",
    "€": "EUR",
    "eur": "EUR",
    "евро": "EUR",
}

# --------------------------------------------------------------------------
# BRAND DETECTION KEYWORDS
# Presence of these in text implies brand = "Apple"
# --------------------------------------------------------------------------
APPLE_KEYWORDS: set[str] = {
    "iphone",
    "airpods",
    "apple watch",
    "macbook",
    "ipad",
    "mac mini",
    "mac studio",
    "apple",
    "app",  # short for AirPods Pro
    "aw",   # short for Apple Watch
    "mba",  # MacBook Air
    "mbp",  # MacBook Pro
}

# --------------------------------------------------------------------------
# Words to ignore / strip from model matching
# --------------------------------------------------------------------------
NOISE_WORDS: set[str] = {
    "apple",
    "iphone",
    "/",
    "-",
    "|",
    "•",
    "·",
    ",",
    ".",
    ":",
    "в наличии",
    "в наличие",
    "есть",
    "stock",
    "available",
    "цена",
    "price",
    "прайс",
}
