import hashlib
import json
import mimetypes
import re
from urllib.parse import urlparse

import requests


AMENITY_PATTERNS = {
    "Lift": [r"\blift\b", r"\belevator\b"],
    "Power Backup": [r"power backup", r"power back.?up", r"generator"],
    "Security": [r"\bsecurity\b", r"\bCCTV\b"],
    "Swimming Pool": [r"swimming pool", r"\bpool\b"],
    "Gymnasium": [r"\bgym\b", r"gymnasium", r"fitness centre"],
    "Clubhouse": [r"\bclub ?house\b"],
    "Children's Play Area": [r"children.?s play", r"kids play area"],
    "Garden": [r"\bgarden\b", r"landscaped garden"],
    "Parking": [r"\bparking\b", r"car park"],
    "Covered Parking": [r"covered parking"],
    "Visitor Parking": [r"visitor parking"],
    "Fire Safety": [r"fire safety", r"fire alarm", r"fire fighting"],
    "Water Supply": [r"water supply", r"24.?7 water"],
    "Rainwater Harvesting": [r"rainwater harvesting"],
    "Intercom": [r"\bintercom\b"],
    "Wi-Fi": [r"\bwi.?fi\b", r"wireless internet"],
    "Air Conditioning": [r"air.?condition", r"\bAC\b"],
    "Vaastu Compliant": [r"vaastu", r"vastu"],
    "Jogging Track": [r"jogging track", r"running track"],
    "Indoor Games": [r"indoor games"],
    "Badminton Court": [r"badminton court"],
    "Tennis Court": [r"tennis court"],
    "Basketball Court": [r"basketball court"],
    "Yoga Room": [r"yoga room", r"yoga studio"],
    "Spa": [r"\bspa\b"],
    "Sauna": [r"\bsauna\b"],
    "Amphitheatre": [r"amphitheatre", r"amphitheater"],
    "Multipurpose Hall": [r"multipurpose hall", r"multi.?purpose hall"],
    "Waste Management": [r"waste management"],
    "Sewage Treatment Plant": [r"sewage treatment", r"\bSTP\b"],
    "Cafeteria": [r"\bcafeteria\b", r"\bcafe\b"],
    "Library": [r"\blibrary\b"],
    "Laundry": [r"\blaundry\b"],
    "Pet Friendly": [r"pet.?friendly", r"pets allowed"],
    "Wheelchair Accessibility": [r"wheelchair", r"disabled access"],
    "Gated Community": [r"gated community"],
    "Earthquake Resistant": [r"earthquake.?resistant"],
    "Solar Lighting": [r"solar lighting", r"solar power"],
    "EV Charging": [r"EV charging", r"electric vehicle charging"],
}
def extract_listings(data):
    """JSON डेटा से listings निकालें."""
    if isinstance(data, list):
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("हर listing JSON object होनी चाहिए।")
        return data

    if isinstance(data, dict):
        for key in (
            "listings", "items", "data", "results",
            "properties", "records"
        ):
            value = data.get(key)
            if isinstance(value, list):
                if not all(isinstance(item, dict) for item in value):
                    raise ValueError(
                        f"{key} में हर listing JSON object होनी चाहिए।"
                    )
                return value
        return [data]

    raise ValueError("JSON का प्रारूप सही नहीं है।")


def get_path(data, path):
    """Nested JSON से value निकालें."""
    current = data

    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif (
            isinstance(current, list)
            and part.isdigit()
            and int(part) < len(current)
        ):
            current = current[int(part)]
        else:
            return None

    return current


def set_path(data, path, value):
    """Nested JSON में value सेट करें."""
    parts = str(path).split(".")
    current = data

    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value


def collect_text(value, output):
    """JSON से amenity matching के लिए text निकालें."""
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                collect_text(item, output)
            elif isinstance(item, (str, int, float)):
                if not re.search(
                    r"url|image|photo|phone|mobile|email|contact",
                    str(key),
                    re.IGNORECASE,
                ):
                    output.append(str(item))

    elif isinstance(value, list):
        for item in value:
            collect_text(item, output)

    elif isinstance(value, str):
        output.append(value)


def find_amenities(source):
    """Keywords से amenities पहचानें."""
    text_parts = []
    collect_text(source, text_parts)
    searchable = " ".join(text_parts)
    found = []

    for amenity, patterns in AMENITY_PATTERNS.items():
        if any(
            re.search(pattern, searchable, re.IGNORECASE)
            for pattern in patterns
        ):
            found.append(amenity)

    for key in (
        "amenities", "features", "facilities", "property_amenities"
    ):
        existing = source.get(key)

        if isinstance(existing, list):
            for item in existing:
                if isinstance(item, str) and item.strip():
                    found.append(item.strip())
                elif isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("title")
                        or item.get("label")
                    )
                    if name:
                        found.append(str(name).strip())

        elif isinstance(existing, str):
            found.extend(
                item.strip()
                for item in re.split(r"[,;|]", existing)
                if item.strip()
            )

    unique = []
    seen = set()

    for item in found:
        normalized = item.casefold()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(item)

    return unique


def transform_listing(source, schema_config=None):
    """Source listing को target JSON में बदलें."""
    if not isinstance(source, dict):
        raise ValueError("Listing JSON object होनी चाहिए।")

    amenities = find_amenities(source)

    if not schema_config:
        output = dict(source)
        output["amenities"] = amenities
        return output

    template = schema_config.get("template", {})
    field_map = schema_config.get("field_map", {})

    if not isinstance(template, dict):
        raise ValueError("'template' JSON object होना चाहिए।")

    if not isinstance(field_map, dict):
        raise ValueError("'field_map' JSON object होना चाहिए।")

    output = json.loads(json.dumps(template, ensure_ascii=False))

    for target_path, source_path in field_map.items():
        value = get_path(source, source_path)
        if value is not None:
            set_path(output, target_path, value)

    set_path(
        output,
        schema_config.get("amenities_target", "amenities"),
        amenities,
    )

    return output
