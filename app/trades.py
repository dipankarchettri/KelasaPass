"""Trade taxonomy with multilingual keywords (English, Kannada, Hindi).

Speech-to-text on Indian voice notes is often code-mixed ("naanu electrician"),
so each trade lists English, Kannada and Hindi forms. NCO-2015 family codes are
indicative only and must be checked against the official NCO list before use.
"""

TRADES = {
    "electrician": {
        "kn": "ಎಲೆಕ್ಟ್ರಿಷಿಯನ್", "hi": "इलेक्ट्रीशियन", "nco": "7411",
        "keywords": ["electrician", "electric", "wiring", "ಎಲೆಕ್ಟ್ರಿಷಿಯನ್", "ವಿದ್ಯುತ್", "ವೈರಿಂಗ್",
                     "इलेक्ट्रीशियन", "बिजली", "वायरिंग"],
    },
    "plumber": {
        "kn": "ಪ್ಲಂಬರ್", "hi": "प्लंबर", "nco": "7126",
        "keywords": ["plumber", "plumbing", "pipe", "ಪ್ಲಂಬರ್", "ನಲ್ಲಿ", "ಪೈಪ್", "प्लंबर", "नल", "पाइप"],
    },
    "mason": {
        "kn": "ಗಾರೆ ಕೆಲಸಗಾರ", "hi": "राजमिस्त्री", "nco": "7112",
        "keywords": ["mason", "masonry", "brick", "ಗಾರೆ", "ಮೇಸ್ತ್ರಿ", "ಇಟ್ಟಿಗೆ", "राजमिस्त्री", "मिस्त्री", "ईंट"],
    },
    "painter": {
        "kn": "ಪೇಂಟರ್", "hi": "पेंटर", "nco": "7131",
        "keywords": ["painter", "painting", "paint", "ಪೇಂಟರ್", "ಬಣ್ಣ", "ಪೇಂಟ್", "पेंटर", "पेंट", "रंगाई"],
    },
    "carpenter": {
        "kn": "ಬಡಗಿ", "hi": "बढ़ई", "nco": "7115",
        "keywords": ["carpenter", "carpentry", "wood", "ಬಡಗಿ", "ಮರಗೆಲಸ", "बढ़ई", "कारपेंटर"],
    },
    "tile_layer": {
        "kn": "ಟೈಲ್ಸ್ ಕೆಲಸಗಾರ", "hi": "टाइल मिस्त्री", "nco": "7122",
        "keywords": ["tile", "tiles", "flooring", "ಟೈಲ್ಸ್", "ಟೈಲ್", "टाइल"],
    },
    "welder": {
        "kn": "ವೆಲ್ಡರ್", "hi": "वेल्डर", "nco": "7212",
        "keywords": ["welder", "welding", "ವೆಲ್ಡರ್", "ವೆಲ್ಡಿಂಗ್", "वेल्डर", "वेल्डिंग"],
    },
    "helper": {
        "kn": "ಸಹಾಯಕ / ಕೂಲಿ", "hi": "हेल्पर / मज़दूर", "nco": "9313",
        "keywords": ["helper", "labour", "labor", "coolie", "ಕೂಲಿ", "ಸಹಾಯಕ", "हेल्पर", "मज़दूर", "मजदूर"],
    },
    "driver": {
        "kn": "ಚಾಲಕ", "hi": "ड्राइवर", "nco": "8322",
        "keywords": ["driver", "driving", "ಡ್ರೈವರ್", "ಚಾಲಕ", "ड्राइवर", "चालक"],
    },
}


def detect_trade(text: str):
    t = text.lower()
    best, hits = None, 0
    for trade, info in TRADES.items():
        n = sum(1 for k in info["keywords"] if k.lower() in t)
        if n > hits:
            best, hits = trade, n
    return best


def trade_label(trade: str, lang: str = "en") -> str:
    if trade not in TRADES:
        return trade or "?"
    if lang == "en":
        return trade.replace("_", " ")
    return TRADES[trade].get(lang, trade)
