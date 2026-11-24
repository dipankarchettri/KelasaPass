"""Tumakuru localities and distance helpers.

Coordinates are approximate demo values around Tumakuru city, good enough to
rank by distance. Production would geocode with Amazon Location Service or a
shared WhatsApp location pin.
"""
import math

LOCALITIES = {
    "ss puram": {"kn": "ಎಸ್ ಎಸ್ ಪುರಂ", "lat": 13.3430, "lon": 77.1070},
    "batawadi": {"kn": "ಬಟವಾಡಿ", "lat": 13.3560, "lon": 77.1050},
    "kyathasandra": {"kn": "ಕ್ಯಾತಸಂದ್ರ", "lat": 13.3200, "lon": 77.1300},
    "siddaganga": {"kn": "ಸಿದ್ದಗಂಗಾ", "lat": 13.3170, "lon": 77.1350},
    "gubbi gate": {"kn": "ಗುಬ್ಬಿ ಗೇಟ್", "lat": 13.3430, "lon": 77.0880},
    "shettihalli": {"kn": "ಶೆಟ್ಟಿಹಳ್ಳಿ", "lat": 13.3600, "lon": 77.1200},
    "antharasanahalli": {"kn": "ಅಂತರಸನಹಳ್ಳಿ", "lat": 13.3100, "lon": 77.0900},
    "tumakuru": {"kn": "ತುಮಕೂರು", "lat": 13.3409, "lon": 77.1010},
}


def detect_locality(text: str):
    t = text.lower()
    # check specific localities before the city name
    for name, info in sorted(LOCALITIES.items(), key=lambda kv: kv[0] == "tumakuru"):
        aliases = [name, info["kn"], name.replace(" ", "")]
        if name == "tumakuru":
            aliases += ["tumkur"]
        if any(a.lower() in t for a in aliases):
            return name
    return None


def coords(locality: str):
    info = LOCALITIES.get(locality) or LOCALITIES["tumakuru"]
    return info["lat"], info["lon"]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
