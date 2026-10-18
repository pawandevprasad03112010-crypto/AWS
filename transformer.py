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
