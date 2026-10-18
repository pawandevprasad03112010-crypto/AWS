import hashlib
import ipaddress
import mimetypes
import os
import re
import socket
from urllib.parse import urlparse

import requests

# Broad rule-based library for common Indian and international real-estate listings.
# Matching means the feature is mentioned in source text; it does not verify availability.
AMENITY_PATTERNS = {
    # Swimming / water
    "Swimming Pool": [r"\bswimming pools?\b", r"\bswimming pool\b", r"\bpoolside\b", r"\bpool\b"],
    "Kids' Pool": [r"\bkids'? pool\b", r"\bchildren'?s pool\b", r"\bkiddie pool\b"],
    "Indoor Swimming Pool": [r"\bindoor swimming pool\b", r"\bcovered swimming pool\b"],
    "Jacuzzi": [r"\bjacuzzi\b", r"\bwhirlpool bath\b"],
    "Water Park": [r"\bwater park\b", r"\bwaterpark\b", r"\bsplash park\b"],
    "Water Body": [r"\bwater bod(?:y|ies)\b", r"\bartificial lake\b", r"\bwater feature\b"],
    # Fitness and wellness
    "Gymnasium": [r"\bgym(?:nasium)?\b", r"\bfitness cent(?:er|re)\b", r"\bfitness studio\b", r"\bhealth club\b"],
    "Yoga/Meditation Room": [r"\byoga (?:room|studio|deck|center|centre)\b", r"\bmeditation (?:room|hall|area|center|centre)\b", r"\byoga and meditation\b"],
    "Aerobics Room": [r"\baerobics (?:room|studio|center|centre)\b"],
    "Spa": [r"\bspa\b", r"\bwellness spa\b"],
    "Sauna": [r"\bsauna\b"],
    "Steam Room": [r"\bsteam room\b", r"\bsteam bath\b"],
    "Jogging Track": [r"\bjogging track\b", r"\bjogging path\b", r"\brunning track\b"],
    "Walking Track": [r"\bwalking track\b", r"\bwalking trail\b", r"\bwalking path\b"],
    "Cycling Track": [r"\bcycling track\b", r"\bbicycle track\b", r"\bcycle track\b"],
    "Reflexology Path": [r"\breflexology (?:path|park|walk)\b"],
    "Open Gym": [r"\bopen[- ]air gym\b", r"\boutdoor gym\b"],
    # Indoor games
    "Indoor Games": [r"\bindoor games?\b", r"\bgames room\b", r"\bindoor recreation\b"],
    "Table Tennis": [r"\btable tennis\b", r"\bping pong\b"],
    "Billiards/Pool Table": [r"\bbilliards?\b", r"\bpool table\b", r"\bsnooker\b"],
    "Carrom": [r"\bcarrom\b"],
    "Chess Room": [r"\bchess room\b", r"\bchess area\b"],
    "Foosball": [r"\bfoosball\b", r"\btable football\b"],
    "Bowling Alley": [r"\bbowling alley\b"],
    "Squash Court": [r"\bsquash court\b"],
    "Badminton Court": [r"\bbadminton courts?\b"],
    "Tennis Court": [r"\btennis courts?\b"],
    "Basketball Court": [r"\bbasketball courts?\b"],
    "Volleyball Court": [r"\bvolleyball courts?\b"],
    "Cricket Pitch/Practice Nets": [r"\bcricket (?:pitch|ground|nets?|practice area)\b", r"\bcricket practice nets?\b"],
    "Football Ground": [r"\bfootball (?:ground|field|pitch)\b", r"\bsoccer field\b"],
    "Skating Rink": [r"\bskating rink\b", r"\bskating area\b"],
    "Golf Course/Putting Green": [r"\bgolf course\b", r"\bputting green\b", r"\bgolf simulator\b"],
    "Outdoor Sports Facilities": [r"\boutdoor sports (?:facilities|area|court)\b", r"\bsports complex\b"],
    # Community and leisure
    "Clubhouse": [r"\bclub ?house\b", r"\bcommunity club\b"],
    "Community Hall": [r"\bcommunity hall\b", r"\bcommunity center\b", r"\bcommunity centre\b"],
    "Multipurpose Hall": [r"\bmulti[- ]purpose hall\b", r"\bmultipurpose hall\b", r"\bmultipurpose room\b"],
    "Party Hall": [r"\bparty hall\b", r"\bcelebration hall\b", r"\bbanquet hall\b"],
    "Banquet Hall": [r"\bbanquet hall\b", r"\bfunction hall\b"],
    "Amphitheatre": [r"\bamphithe(?:a|e)tre\b", r"\bopen[- ]air theatre\b"],
    "Mini Theatre": [r"\bmini[- ]?theatre\b", r"\bmini[- ]?theater\b", r"\bprivate cinema\b"],
    "Home Theatre": [r"\bhome[- ]theatre\b", r"\bhome[- ]theater\b"],
    "Library": [r"\blibrary\b", r"\breading room\b", r"\breading lounge\b"],
    "Co-working Space": [r"\bco[- ]?working (?:space|area|lounge)\b", r"\bbusiness center\b", r"\bbusiness centre\b"],
    "Conference Room": [r"\bconference room\b", r"\bmeeting room\b"],
    "Cafeteria": [r"\bcafeteria\b", r"\bcanteen\b", r"\bfood court\b"],
    "Convenience Store": [r"\bconvenience store\b", r"\bprovision store\b", r"\bon[- ]site shop\b"],
    "Rooftop Lounge": [r"\brooftop lounge\b", r"\broof[- ]top lounge\b", r"\bsky lounge\b"],
    "Rooftop Garden": [r"\brooftop garden\b", r"\bterrace garden\b", r"\bsky garden\b"],
    "Barbecue Area": [r"\bbarbecue area\b", r"\bbbq area\b", r"\bbarbeque\b", r"\bbarbecue pit\b"],
    "Music Room": [r"\bmusic room\b", r"\bmusic studio\b"],
    "Dance Studio": [r"\bdance studio\b", r"\bdance room\b"],
    "Hobby Room": [r"\bhobby room\b", r"\bactivity room\b"],
    # Outdoor / family / pets
    "Children's Play Area": [r"\bchildren'?s play(?:ground)? area\b", r"\bkids'? play area\b", r"\bchildrens? park\b", r"\bplayground\b"],
    "Indoor Kids' Play Area": [r"\bindoor (?:kids|children)'?s? play area\b", r"\bsoft play area\b"],
    "Creche/Day Care": [r"\bcr[eè]che\b", r"\bday[- ]care (?:center|centre)\b", r"\bchild care center\b"],
    "Landscaped Garden": [r"\blandscaped gardens?\b", r"\blandscaping\b"],
    "Garden": [r"\bgardens?\b", r"\bgreen garden\b"],
    "Park": [r"\bpark\b", r"\bcentral park\b", r"\bcommunity park\b"],
    "Herbal Garden": [r"\bherbal garden\b", r"\bmedicinal garden\b"],
    "Butterfly Garden": [r"\bbutterfly garden\b"],
    "Kitchen Garden": [r"\bkitchen garden\b", r"\bvegetable garden\b"],
    "Senior Citizens' Area": [r"\bsenior citizens?'? (?:area|corner|sit[- ]?out)\b", r"\belderly sit[- ]?out\b"],
    "Pet-Friendly Area": [r"\bpet[- ]friendly (?:area|zone|space|community)\b", r"\bpet park\b", r"\bdog park\b", r"\bdog run\b"],
    "Pet Washing/Grooming Area": [r"\bpet (?:wash|washing|grooming) (?:area|station|room)\b", r"\bdog wash\b"],
    "Senior Living Facilities": [r"\bsenior living facilit(?:y|ies)\b", r"\bassisted living\b"],
    "Picnic Area": [r"\bpicnic area\b", r"\bpavilion\b"],
    "Outdoor Seating": [r"\boutdoor seating\b", r"\bsit[- ]out area\b", r"\bseating plaza\b"],
    "Ample Open Space": [r"\bopen spaces?\b", r"\bopen green spaces?\b", r"\bcentral courtyard\b"],
    # Safety / building systems
    "24x7 Security": [r"\b24\s*[/x-]\s*7 security\b", r"\bround[- ]the[- ]clock security\b", r"\baround[- ]the[- ]clock security\b"],
    "Security": [r"\bsecurity guards?\b", r"\bsecurity personnel\b", r"\bsecurity services?\b"],
    "CCTV Surveillance": [r"\bcctv\b", r"\bvideo surveillance\b", r"\bsurveillance cameras?\b"],
    "Gated Community": [r"\bgated communit(?:y|ies)\b", r"\bgated complex\b", r"\bgated entrance\b"],
    "Access Control": [r"\baccess control\b", r"\bcontrolled access\b", r"\bsecure entry\b"],
    "Intercom": [r"\bintercom\b", r"\baudio intercom\b"],
    "Video Door Phone": [r"\bvideo door phone\b", r"\bvideo doorbell\b", r"\bvideo intercom\b"],
    "Fire Safety": [r"\bfire safety\b", r"\bfire[- ]fighting\b", r"\bfire alarm\b", r"\bfire extinguisher\b"],
    "Smoke Detector": [r"\bsmoke detectors?\b", r"\bsmoke alarm\b"],
    "Sprinkler System": [r"\bsprinkler system\b", r"\bfire sprinklers?\b"],
    "Earthquake Resistant Structure": [r"\bearthquake[- ]resistant\b", r"\bseismic resistant\b"],
    "Video Surveillance": [r"\bvideo surveillance\b"],
    "Visitor Management": [r"\bvisitor management\b", r"\bvisitor registration\b"],
    "Concierge": [r"\bconcierge\b", r"\bdoorman\b", r"\bdoor attendant\b"],
    "Reception/Lobby": [r"\breception lobby\b", r"\bgrand lobby\b", r"\bentrance lobby\b", r"\breception area\b"],
    "Property Management Office": [r"\bproperty management office\b", r"\bon[- ]site management\b"],
    # Parking / transport
    "Car Parking": [r"\bcar parking\b", r"\bparking spaces?\b", r"\bparking facility\b", r"\bvehicle parking\b"],
    "Covered Parking": [r"\bcovered parking\b", r"\bcovered car park(?:ing)?\b", r"\bsheltered parking\b"],
    "Open Parking": [r"\bopen parking\b", r"\bopen car park(?:ing)?\b"],
    "Basement Parking": [r"\bbasement parking\b", r"\bparking basement\b"],
    "Stilt Parking": [r"\bstilt parking\b"],
    "Visitor Parking": [r"\bvisitor parking\b", r"\bguest parking\b"],
    "Reserved Parking": [r"\breserved parking\b", r"\ballotted parking\b", r"\bdedicated parking\b"],
    "Valet Parking": [r"\bvalet parking\b"],
    "EV Charging": [r"\bev charging\b", r"\belectric vehicle charging\b", r"\be[- ]vehicle charging\b", r"\bev charging station\b"],
    "Two-Wheeler Parking": [r"\btwo[- ]wheeler parking\b", r"\bbike parking\b", r"\bscooter parking\b"],
    "Bicycle Storage": [r"\bbicycle storage\b", r"\bbike storage\b", r"\bcycle storage\b"],
    "Car Wash Area": [r"\bcar wash(?:ing)? (?:area|facility|bay)\b"],
    "Driver's Rest Room": [r"\bdrivers?'? rest room\b", r"\bdriver lounge\b"],
    "Bus/Shuttle Service": [r"\bshuttle service\b", r"\bcommunity shuttle\b", r"\bbus service\b"],
    # Utilities / sustainability
    "Power Backup": [r"\bpower backup\b", r"\bpower back[- ]?up\b", r"\bgenerator backup\b", r"\bdg backup\b"],
    "100% Power Backup": [r"\b100\s*% power backup\b", r"\bfull power backup\b", r"\bcomplete power backup\b"],
    "Water Supply": [r"\b24\s*[/x-]\s*7 water supply\b", r"\bround[- ]the[- ]clock water supply\b", r"\bwater supply\b"],
    "Rainwater Harvesting": [r"\brainwater harvesting\b", r"\brain water harvesting\b"],
    "Sewage Treatment Plant": [r"\bsewage treatment plant\b", r"\bstp\b"],
    "Waste Management": [r"\bwaste management\b", r"\bsolid waste management\b", r"\bwaste segregation\b"],
    "Organic Waste Converter": [r"\borganic waste converter\b", r"\borganic waste compost(?:er|ing)\b"],
    "Solar Panels": [r"\bsolar panels?\b", r"\bsolar power\b", r"\bsolar energy\b"],
    "Energy Efficient Lighting": [r"\benergy[- ]efficient lighting\b", r"\bled lighting\b", r"\bsensor lights?\b"],
    "Rainwater Recharge": [r"\bgroundwater recharge\b", r"\bwater recharge pits?\b", r"\brecharge pits?\b"],
    "Water Conservation": [r"\bwater conservation\b", r"\bwater[- ]saving systems?\b"],
    "EV-Friendly Infrastructure": [r"\bev[- ]ready\b", r"\bev[- ]friendly infrastructure\b"],
    "Green Building": [r"\bgreen building\b", r"\bgreen certified\b", r"\bleed certified\b", r"\bigbc\b"],
    "Energy Efficient Building": [r"\benergy[- ]efficient building\b", r"\benergy efficiency\b"],
    # Access / common facilities
    "Lift": [r"\blifts?\b", r"\belevators?\b"],
    "Service Lift": [r"\bservice lifts?\b", r"\bfreight elevators?\b"],
    "High-Speed Elevators": [r"\bhigh[- ]speed elevators?\b", r"\bhigh[- ]speed lifts?\b"],
    "Wheelchair Accessibility": [r"\bwheelchair accessible\b", r"\bwheelchair accessibility\b", r"\bramp access\b"],
    "Accessibility Features": [r"\baccessible entrance\b", r"\bbarrier[- ]free\b", r"\bdisabled[- ]friendly\b"],
    "Wide Corridors": [r"\bwide corridors?\b", r"\bwide hallways?\b"],
    "Service Entrance": [r"\bservice entrance\b", r"\bseparate service entry\b"],
    "Storage Space": [r"\bstorage space\b", r"\bstorage room\b", r"\bstorage lockers?\b"],
    "Servant Room/Quarter": [r"\bservant(?:'s)? (?:room|quarter|quarters)\b", r"\bmaid(?:'s)? room\b"],
    "Laundry Facility": [r"\blaundry facilit(?:y|ies)\b", r"\blaundry room\b", r"\bon[- ]site laundry\b"],
    "Housekeeping": [r"\bhousekeeping\b", r"\bcleaning service\b"],
    "Maintenance Staff": [r"\bmaintenance staff\b", r"\bon[- ]site maintenance\b", r"\bmaintenance service\b"],
    "Wi-Fi/Internet": [r"\bwi[- ]?fi\b", r"\bhigh[- ]speed internet\b", r"\bbroadband connectivity\b"],
    "Mobile Network Connectivity": [r"\bmobile network coverage\b", r"\bnetwork connectivity\b"],
    "Smart Home Automation": [r"\bsmart home automation\b", r"\bhome automation\b", r"\bsmart home\b"],
    "Smart Locks": [r"\bsmart locks?\b", r"\bdigital door locks?\b"],
    "Video Doorbell": [r"\bvideo doorbell\b"],
    "Central Air Conditioning": [r"\bcentral air[- ]?conditioning\b", r"\bcentral ac\b"],
    "Air Conditioning": [r"\bair[- ]?conditioning\b", r"\bair conditioned\b", r"\bac provision\b"],
    "Modular Kitchen": [r"\bmodular kitchen\b", r"\bmodular cabinetry\b"],
    "Wardrobes": [r"\bwardrobes?\b", r"\bwalk[- ]in closets?\b", r"\bbuilt[- ]in closets?\b"],
    "Balcony": [r"\bbalcon(?:y|ies)\b", r"\bprivate balcony\b"],
    "Private Terrace": [r"\bprivate terrace\b", r"\bprivate roof terrace\b"],
    "Deck/Patio": [r"\bdeck\b", r"\bpatio\b"],
    "Serviced Apartment Facilities": [r"\bserviced apartment\b", r"\bserviced residence\b"],
    "Furnished": [r"\bfully furnished\b", r"\bsemi[- ]furnished\b", r"\bfurnished apartment\b"],
    "Double Glazed Windows": [r"\bdouble[- ]glazed windows?\b", r"\bdg windows?\b"],
    "Vastu Compliant": [r"\bvastu compliant\b", r"\bvastu friendly\b", r"\bvaastu compliant\b"],
    "Piped Gas": [r"\bpiped gas\b", r"\bpiped natural gas\b", r"\bpng connection\b"],
    "RO Water System": [r"\bro water\b", r"\breverse osmosis\b", r"\bwater purifier\b"],
    "Water Softener": [r"\bwater softener\b", r"\bwater softening plant\b"],
    "High Ceilings": [r"\bhigh ceilings?\b", r"\bdouble[- ]height ceiling\b"],
    "Premium Flooring": [r"\bmarble flooring\b", r"\bgranite flooring\b", r"\bwooden flooring\b", r"\bvitrified tiles?\b"],
    "Fireplace": [r"\bfireplace\b"],
    "Study Room": [r"\bstudy room\b", r"\bstudy area\b", r"\bhome office\b"],
    "Walk-in Closet": [r"\bwalk[- ]in closet\b", r"\bwalk[- ]in wardrobe\b"],
    "Private Garden": [r"\bprivate garden\b", r"\bpersonal garden\b"],
    "Private Pool": [r"\bprivate swimming pool\b", r"\bprivate pool\b"],
    "Terrace": [r"\bterrace\b", r"\bopen terrace\b"],
    "View of Landmark/Nature": [r"\bsea view\b", r"\blake view\b", r"\bmountain view\b", r"\bpark view\b", r"\bgarden view\b"],
    # Commercial / office / retail
    "Reception Area": [r"\breception area\b", r"\bfront desk\b"],
    "Retail Shops": [r"\bretail shops?\b", r"\bshopping arcade\b", r"\bcommercial shops?\b"],
    "ATM": [r"\batm\b", r"\batm kiosk\b"],
    "Bank/Banking Facility": [r"\bbanking facilit(?:y|ies)\b", r"\bon[- ]site bank\b"],
    "Food Court": [r"\bfood court\b", r"\bfood plaza\b"],
    "Loading/Unloading Area": [r"\bloading and unloading\b", r"\bloading bay\b", r"\bunloading area\b"],
    "Goods Lift": [r"\bgoods lifts?\b", r"\bfreight lifts?\b"],
    "High-Speed Internet for Office": [r"\bleased line internet\b", r"\benterprise internet\b"],
    "Conference Facilities": [r"\bconference facilit(?:y|ies)\b", r"\bconference room\b", r"\bboardroom\b"],
    "Fire Exit/Emergency Staircase": [r"\bfire exit\b", r"\bemergency staircase\b", r"\bfire escape\b"],
    # Property / location-linked features sometimes described as amenities
    "Near Public Transport": [r"\bnear (?:metro|bus stop|railway station)\b", r"\bpublic transport access\b", r"\bwalking distance to metro\b"],
    "Near School": [r"\bnearby schools?\b", r"\bclose to schools?\b", r"\bwalking distance to schools?\b"],
    "Near Hospital": [r"\bnearby hospitals?\b", r"\bclose to hospitals?\b", r"\bnear hospital\b"],
    "Near Shopping Centre": [r"\bnearby shopping\b", r"\bshopping mall nearby\b", r"\bclose to (?:mall|market)\b"],
    "Highway Connectivity": [r"\bhighway connectivity\b", r"\bnear (?:the )?highway\b", r"\bexpressway connectivity\b"],
    "Corner Property": [r"\bcorner plot\b", r"\bcorner property\b", r"\bcorner unit\b"],
    "East Facing": [r"\beast[- ]facing\b", r"\bfacing east\b"],
    "North Facing": [r"\bnorth[- ]facing\b", r"\bfacing north\b"],
    "Park Facing": [r"\bpark[- ]facing\b", r"\bfacing (?:the )?park\b"],
}

NEGATION_PATTERNS = [
    r"\bno\b", r"\bnot available\b", r"\bnot provided\b", r"\bwithout\b",
    r"\bdoes not have\b", r"\bdo not have\b", r"\bdoesn't have\b",
    r"\bnot included\b", r"\bnot offered\b", r"\babsent\b",
    r"\bunder construction\b", r"\bproposed\b", r"\bcoming soon\b",
]


def extract_listings(data):
    if isinstance(data, list):
        result = [x for x in data if isinstance(x, dict)]
        if len(result) != len(data):
            raise ValueError("JSON array में कुछ entries object नहीं हैं।")
        return result
    if isinstance(data, dict):
        for key in ("listings", "items", "data", "results", "properties", "records"):
            if isinstance(data.get(key), list):
                result = [x for x in data[key] if isinstance(x, dict)]
                if len(result) != len(data[key]):
                    raise ValueError(f"'{key}' array में कुछ entries object नहीं हैं।")
                return result
        if any(key in data for key in ("title", "listing", "property", "media", "pricing", "location", "amenities")):
            return [data]
    raise ValueError("JSON root array होना चाहिए, या listings/items/data/results/properties/records में array होनी चाहिए।")


def validate_schema_config(config):
    if not isinstance(config, dict):
        raise ValueError("Schema config JSON object होना चाहिए।")
    if not isinstance(config.get("template"), dict):
        raise ValueError("Schema config में 'template' नाम का JSON object जरूरी है।")
    if not isinstance(config.get("field_map", {}), dict):
        raise ValueError("'field_map' JSON object होना चाहिए।")
    if not isinstance(config.get("amenities_target", "amenities"), str):
        raise ValueError("'amenities_target' string होना चाहिए。")


def get_path(obj, path):
    current = obj
    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def set_path(obj, path, value):
    parts = str(path).split(".")
    current = obj
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def collect_text(value, out, key=""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            # Only skip URLs/IDs/contact details; search descriptive strings throughout nested records.
            if isinstance(child, (str, int, float)) and not re.search(
                r"url|image|photo|(^|_)id$|phone|mobile|email|contact|latitude|longitude", str(child_key), re.I
            ):
                out.append(str(child))
            else:
                collect_text(child, out, str(child_key))
    elif isinstance(value, list):
        for child in value:
            collect_text(child, out, key)
    elif isinstance(value, str):
        out.append(value)


def _has_nearby_negation(text, start, end):
    # Check a short window before a match for a negation or uncertain-status phrase.
    before = text[max(0, start - 45):start]
    after = text[end:min(len(text), end + 25)]
    return any(re.search(pattern + r"(?:\s+\w+){0,5}\s*$", before, re.I) for pattern in NEGATION_PATTERNS) or any(
        re.search(r"^\s*(?:is )?(?:not available|not provided|not included|under construction|proposed|coming soon)\b", after, re.I)
    )


def find_amenities(source):
    found = []

    def add_explicit(value):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    found.append(item.strip())
                elif isinstance(item, dict):
                    label = item.get("name") or item.get("title") or item.get("label") or item.get("amenity")
                    if label and str(label).strip():
                        found.append(str(label).strip())
        elif isinstance(value, str):
            found.extend(x.strip() for x in re.split(r"[,;|]", value) if x.strip())
        elif isinstance(value, dict):
            for key, val in value.items():
                                if val is True:
                    found.append(str(key).replace("_", " ").strip())
                elif isinstance(val, (str, list, dict)):
                    add_explicit(val)

    # Structured amenities/features have priority and are preserved.
    for key in ("amenities", "features", "facilities", "property_amenities"):
        if key in source:
            add_explicit(source[key])

    text_parts = []
    collect_text(source, text_parts)
    searchable = re.sub(r"\s+", " ", " ".join(text_parts).lower())

    for label, patterns in AMENITY_PATTERNS.items():
        matched = False
        for pattern in patterns:
            for match in re.finditer(pattern, searchable, re.I):
                if not _has_nearby_negation(
                    searchable, match.start(), match.end()
                ):
                    matched = True
                    break
            if matched:
                break
        if matched:
            found.append(label)

    result, seen = [], set()
    for item in found:
        clean = re.sub(r"\s+", " ", str(item)).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _first_value(source, paths, default=None):
    """Return the first present, non-empty value from dotted paths."""
    for path in paths:
        value = get_path(source, path)
        if value is not None and value != "":
            return value
    return default


def _number(value):
    """Convert numeric-looking values to numbers."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    cleaned = re.sub(
        r"[^0-9.\-]", "", str(value).replace(",", "")
    )
    try:
        number = float(cleaned)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return None


def _as_text(value, default=""):
    if value is None or isinstance(value, (dict, list)):
        return default
    return str(value)


def _image_urls(source):
    """Collect URLs from known image/media fields."""
    result = []
    media = source.get("media") if isinstance(source.get("media"), dict) else {}
    candidate_keys = (
        "main_image", "image_url", "photo_url", "thumbnail_url",
        "image", "images", "photos", "pictures", "gallery",
        "prop_images"
    )

    def add(value):
        if isinstance(value, str):
            url = value.strip()
            if url.startswith(("https://", "http://")) and url not in result:
                result.append(url)
        elif isinstance(value, dict):
            for key in (
                "url", "src", "image_url", "original_url",
                "large_url", "full_url", "thumbnail_url",
                "photo_url", "cdn_url"
            ):
                if key in value:
                    add(value[key])
        elif isinstance(value, list):
            for item in value:
                add(item)

    for key in candidate_keys:
        if key in media:
            add(media[key])

    for parent in (
        source,
        source.get("property", {}),
        source.get("entity", {}),
        source.get("listing", {}),
    ):
        if isinstance(parent, dict):
            for key in candidate_keys:
                if key in parent:
                    add(parent[key])

    return result
    def transform_listing(source, schema_config=None):
    """Transform one listing into the configured template."""
    if not isinstance(source, dict):
        raise ValueError("Listing record JSON object नहीं है।")

    amenities = find_amenities(source)

    if not schema_config:
        import copy
        output = copy.deepcopy(source)
        output["amenities"] = amenities
        return output

    validate_schema_config(schema_config)
    import copy
    output = copy.deepcopy(schema_config["template"])

    title = _first_value(
        source, ["entity.title", "listing.title", "title"]
    )
    description = _first_value(
        source,
        ["entity.description", "listing.description", "description"]
    )

    for target, value in (
        ("entity.title", title),
        ("listing.title", title),
        ("entity.description", description),
        ("listing.description", description),
    ):
        if value is not None:
            set_path(output, target, value)

    registered = _first_value(
        source,
        ["availability.registered_display", "listing.registered_display"]
    )
    if registered is not None:
        set_path(output, "listing.registered_display", registered)

    market = _first_value(source, ["listing.market", "market"])
    if market is not None:
        set_path(output, "listing.market", market)

    price_text = _first_value(source, [
        "pricing.display_price",
        "pricing.localized_price_text",
        "localized_price_text",
        "localized_price",
        "pricing.price",
        "price",
    ])
    price_words = _first_value(
        source, ["pricing.price_in_words", "price_in_words"]
    )

    if price_text is not None:
        set_path(output, "pricing.display_price", _as_text(price_text))
    if price_words is not None:
        set_path(output, "pricing.price_in_words", _as_text(price_words))

    price_per_area = _first_value(source, [
        "pricing.price_per_unit_area",
        "pricing.localized_price_sqft_text",
        "localized_price_sqft_text",
    ])
    if price_per_area is not None:
        set_path(
            output, "pricing.price_per_unit_area",
            _as_text(price_per_area)
        )

    price_sqft = _first_value(source, [
        "pricing.price_sqft",
        "pricing.localized_price_sqft",
        "localized_price_sqft",
    ])
    if price_sqft is not None:
        set_path(output, "pricing.price_sqft", _number(price_sqft))

    for target, paths in {
        "pricing.min_price": [
            "pricing.min_price", "pricing.min_price_value", "min_price"
        ],
        "pricing.max_price": [
            "pricing.max_price", "pricing.max_price_value", "max_price"
        ],
        "pricing.average_price": [
            "pricing.average_price",
            "pricing.average_price_value",
            "average_price",
        ],
        "pricing.brokerage": ["pricing.brokerage", "brokerage"],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            parsed = (
                _number(value)
                if target != "pricing.brokerage"
                else value
            )
            if parsed is not None:
                set_path(output, target, parsed)

    property_paths = {
        "property.bedrooms": ["property.bedrooms", "bedrooms"],
        "property.bathrooms": ["property.bathrooms", "bathrooms"],
        "property.balconies": ["property.balconies", "balconies"],
        "property.furnishing": [
            "property.furnishing",
            "property.furnishing_label",
            "furnishing",
        ],
        "property.floor_number": [
            "property.floor_number", "property.floor", "floor_number"
        ],
        "property.floor_numbers": [
            "property.floor_numbers", "floor_numbers"
        ],
        "property.total_floors": [
            "property.total_floors", "total_floors"
        ],
        "property.ownership_type": [
            "property.ownership_label",
            "property.ownership_type",
            "ownership_type",
        ],
        "property.property_age": [
            "property.property_age",
            "property.age",
            "property.age_label",
            "property.age_code",
        ],
        "property.area.display_area": [
            "property.area.display_area", "localized_area"
        ],
        "property.area.secondary_area": [
            "property.area.secondary_area",
            "localized_secondary_area",
        ],
        "property.area.carpet_area": [
            "property.area.carpet_area",
            "property.area.carpet_sqft",
            "localized_carpet_area",
            "localized_area_value",
        ],
    }

    for target, paths in property_paths.items():
        value = _first_value(source, paths)
        if value is not None:
            if target.endswith((
                "bedrooms", "bathrooms", "balconies",
                "total_floors", "carpet_area"
            )):
                value = _number(value)
            if value is not None:
                set_path(output, target, value)

    floor_numbers = _first_value(
        source, ["property.floor_numbers", "floor_numbers"]
    )
    if isinstance(floor_numbers, list):
        set_path(output, "property.floor_numbers", floor_numbers)
    elif floor_numbers is None:
        floor = _number(
            _first_value(source, ["property.floor_number", "floor_number"])
        )
        if floor is not None:
            set_path(output, "property.floor_numbers", [floor])

    parking = _first_value(source, [
        "property.reserved_parking.covered",
        "property.reserved_parking.c",
        "property.covered_parking",
    ])
    if parking is not None:
        set_path(
            output, "property.reserved_parking.covered",
            _number(parking) or 0
        )

    for target, paths in {
        "location.city": ["location.city", "city"],
        "location.locality": ["location.locality", "locality"],
        "location.locality_without_city": [
            "location.locality_without_city"
        ],
        "location.locality_name": ["location.locality_name"],
        "location.building_name": [
            "location.building_name",
            "relationships.project.building_name",
        ],
        "location.society_name": [
            "location.society_name",
            "relationships.project.project_name",
            "relationships.project.building_name",
        ],
        "location.coordinates.latitude": [
            "location.coordinates.latitude", "coordinates.latitude"
        ],
        "location.coordinates.longitude": [
            "location.coordinates.longitude", "coordinates.longitude"
        ],
        "location.coordinates.zoom_level": [
            "location.coordinates.zoom_level"
        ],
        "location.coordinates.source": [
            "location.coordinates.source"
        ],
        "location.landmarks": ["location.landmarks"],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            if target.endswith(("latitude", "longitude")):
                value = _number(value)
            set_path(output, target, value)

    images = _image_urls(source)
    if images:
        set_path(output, "media.images", images)

    for target, paths in {
        "contact_details.contact_name": [
            "contact_details.contact_name",
            "contact_details.profile.contact_name",
        ],
        "contact_details.company_name": [
            "contact_details.company_name",
            "contact_details.profile.contact_company_name",
        ],
        "contact_details.phone_number": [
            "contact_details.phone_number",
            "contact_details.mobile",
            "contact_details.phone",
        ],
        "contact_details.dealer_photo_url": [
            "contact_details.dealer_photo_url",
            "contact_details.profile.photo_url",
        ],
        "contact_details.class_label": [
            "contact_details.class_label",
            "contact_details.profile.class_label",
        ],
        "contact_details.profile.contact_name": [
            "contact_details.profile.contact_name",
            "contact_details.contact_name",
        ],
        "contact_details.profile.contact_company_name": [
            "contact_details.profile.contact_company_name",
            "contact_details.company_name",
        ],
        "contact_details.profile.phone_number": [
            "contact_details.profile.phone_number",
            "contact_details.phone_number",
        ],
        "contact_details.profile.photo_url": [
            "contact_details.profile.photo_url",
            "contact_details.dealer_photo_url",
        ],
        "contact_details.profile.super.contact_company_name": [
            "contact_details.profile.super.contact_company_name",
            "contact_details.company_name",
        ],
        "contact_details.profile.super.photo_url": [
            "contact_details.profile.super.photo_url",
            "contact_details.dealer_photo_url",
        ],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            set_path(output, target, value)

    for target, paths in {
        "attributes.compliance.registration_status": [
            "attributes.compliance.registration_status",
            "rera.registration_status",
        ],
        "attributes.compliance.rera_registration_id": [
            "attributes.compliance.rera_registration_id",
            "rera_registration_id",
            "rera.rera_registration_id",
        ],
        "attributes.compliance.project_rera_registration_id": [
            "attributes.compliance.project_rera_registration_id",
            "project_rera_registration_id",
            "relationships.project.rera_registration_id",
        ],
        "attributes.tags_and_signals.property_tags": [
            "attributes.tags_and_signals.property_tags", "property_tags"
        ],
        "attributes.tags_and_signals.tags": [
            "attributes.tags_and_signals.tags", "tags"
        ],
        "attributes.tags_and_signals.top_usps": [
            "attributes.tags_and_signals.top_usps",
            "top_usps",
            "source_specific.top_usps",
        ],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            set_path(output, target, value)

    set_path(
        output, schema_config.get("amenities_target", "amenities"),
        amenities
    )

    # Custom field mappings override built-in mappings.
    for target_path, source_path in schema_config.get("field_map", {}).items():
        value = get_path(source, source_path)
        if value is not None:
            set_path(output, target_path, value)

    return output
    def transform_listing(source, schema_config=None):
    """Transform one listing into the configured template."""
    if not isinstance(source, dict):
        raise ValueError("Listing record JSON object नहीं है।")

    amenities = find_amenities(source)

    if not schema_config:
        import copy
        output = copy.deepcopy(source)
        output["amenities"] = amenities
        return output

    validate_schema_config(schema_config)
    import copy
    output = copy.deepcopy(schema_config["template"])

    title = _first_value(
        source, ["entity.title", "listing.title", "title"]
    )
    description = _first_value(
        source,
        ["entity.description", "listing.description", "description"]
    )

    for target, value in (
        ("entity.title", title),
        ("listing.title", title),
        ("entity.description", description),
        ("listing.description", description),
    ):
        if value is not None:
            set_path(output, target, value)

    registered = _first_value(
        source,
        ["availability.registered_display", "listing.registered_display"]
    )
    if registered is not None:
        set_path(output, "listing.registered_display", registered)

    market = _first_value(source, ["listing.market", "market"])
    if market is not None:
        set_path(output, "listing.market", market)

    price_text = _first_value(source, [
        "pricing.display_price",
        "pricing.localized_price_text",
        "localized_price_text",
        "localized_price",
        "pricing.price",
        "price",
    ])
    price_words = _first_value(
        source, ["pricing.price_in_words", "price_in_words"]
    )

    if price_text is not None:
        set_path(output, "pricing.display_price", _as_text(price_text))
    if price_words is not None:
        set_path(output, "pricing.price_in_words", _as_text(price_words))

    price_per_area = _first_value(source, [
        "pricing.price_per_unit_area",
        "pricing.localized_price_sqft_text",
        "localized_price_sqft_text",
    ])
    if price_per_area is not None:
        set_path(
            output, "pricing.price_per_unit_area",
            _as_text(price_per_area)
        )

    price_sqft = _first_value(source, [
        "pricing.price_sqft",
        "pricing.localized_price_sqft",
        "localized_price_sqft",
    ])
    if price_sqft is not None:
        set_path(output, "pricing.price_sqft", _number(price_sqft))

    for target, paths in {
        "pricing.min_price": [
            "pricing.min_price", "pricing.min_price_value", "min_price"
        ],
        "pricing.max_price": [
            "pricing.max_price", "pricing.max_price_value", "max_price"
        ],
        "pricing.average_price": [
            "pricing.average_price",
            "pricing.average_price_value",
            "average_price",
        ],
        "pricing.brokerage": ["pricing.brokerage", "brokerage"],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            parsed = (
                _number(value)
                if target != "pricing.brokerage"
                else value
            )
            if parsed is not None:
                set_path(output, target, parsed)

    property_paths = {
        "property.bedrooms": ["property.bedrooms", "bedrooms"],
        "property.bathrooms": ["property.bathrooms", "bathrooms"],
        "property.balconies": ["property.balconies", "balconies"],
        "property.furnishing": [
            "property.furnishing",
            "property.furnishing_label",
            "furnishing",
        ],
        "property.floor_number": [
            "property.floor_number", "property.floor", "floor_number"
        ],
        "property.floor_numbers": [
            "property.floor_numbers", "floor_numbers"
        ],
        "property.total_floors": [
            "property.total_floors", "total_floors"
        ],
        "property.ownership_type": [
            "property.ownership_label",
            "property.ownership_type",
            "ownership_type",
        ],
        "property.property_age": [
            "property.property_age",
            "property.age",
            "property.age_label",
            "property.age_code",
        ],
        "property.area.display_area": [
            "property.area.display_area", "localized_area"
        ],
        "property.area.secondary_area": [
            "property.area.secondary_area",
            "localized_secondary_area",
        ],
        "property.area.carpet_area": [
            "property.area.carpet_area",
            "property.area.carpet_sqft",
            "localized_carpet_area",
            "localized_area_value",
        ],
    }

    for target, paths in property_paths.items():
        value = _first_value(source, paths)
        if value is not None:
            if target.endswith((
                "bedrooms", "bathrooms", "balconies",
                "total_floors", "carpet_area"
            )):
                value = _number(value)
            if value is not None:
                set_path(output, target, value)

    floor_numbers = _first_value(
        source, ["property.floor_numbers", "floor_numbers"]
    )
    if isinstance(floor_numbers, list):
        set_path(output, "property.floor_numbers", floor_numbers)
    elif floor_numbers is None:
        floor = _number(
            _first_value(source, ["property.floor_number", "floor_number"])
        )
        if floor is not None:
            set_path(output, "property.floor_numbers", [floor])

    parking = _first_value(source, [
        "property.reserved_parking.covered",
        "property.reserved_parking.c",
        "property.covered_parking",
    ])
    if parking is not None:
        set_path(
            output, "property.reserved_parking.covered",
            _number(parking) or 0
        )

    for target, paths in {
        "location.city": ["location.city", "city"],
        "location.locality": ["location.locality", "locality"],
        "location.locality_without_city": [
            "location.locality_without_city"
        ],
        "location.locality_name": ["location.locality_name"],
        "location.building_name": [
            "location.building_name",
            "relationships.project.building_name",
        ],
        "location.society_name": [
            "location.society_name",
            "relationships.project.project_name",
            "relationships.project.building_name",
        ],
        "location.coordinates.latitude": [
            "location.coordinates.latitude", "coordinates.latitude"
        ],
        "location.coordinates.longitude": [
            "location.coordinates.longitude", "coordinates.longitude"
        ],
        "location.coordinates.zoom_level": [
            "location.coordinates.zoom_level"
        ],
        "location.coordinates.source": [
            "location.coordinates.source"
        ],
        "location.landmarks": ["location.landmarks"],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            if target.endswith(("latitude", "longitude")):
                value = _number(value)
            set_path(output, target, value)

    images = _image_urls(source)
    if images:
        set_path(output, "media.images", images)

    for target, paths in {
        "contact_details.contact_name": [
            "contact_details.contact_name",
            "contact_details.profile.contact_name",
        ],
        "contact_details.company_name": [
            "contact_details.company_name",
            "contact_details.profile.contact_company_name",
        ],
        "contact_details.phone_number": [
            "contact_details.phone_number",
            "contact_details.mobile",
            "contact_details.phone",
        ],
        "contact_details.dealer_photo_url": [
            "contact_details.dealer_photo_url",
            "contact_details.profile.photo_url",
        ],
        "contact_details.class_label": [
            "contact_details.class_label",
            "contact_details.profile.class_label",
        ],
        "contact_details.profile.contact_name": [
            "contact_details.profile.contact_name",
            "contact_details.contact_name",
        ],
        "contact_details.profile.contact_company_name": [
            "contact_details.profile.contact_company_name",
            "contact_details.company_name",
        ],
        "contact_details.profile.phone_number": [
            "contact_details.profile.phone_number",
            "contact_details.phone_number",
        ],
        "contact_details.profile.photo_url": [
            "contact_details.profile.photo_url",
            "contact_details.dealer_photo_url",
        ],
        "contact_details.profile.super.contact_company_name": [
            "contact_details.profile.super.contact_company_name",
            "contact_details.company_name",
        ],
        "contact_details.profile.super.photo_url": [
            "contact_details.profile.super.photo_url",
            "contact_details.dealer_photo_url",
        ],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            set_path(output, target, value)

    for target, paths in {
        "attributes.compliance.registration_status": [
            "attributes.compliance.registration_status",
            "rera.registration_status",
        ],
        "attributes.compliance.rera_registration_id": [
            "attributes.compliance.rera_registration_id",
            "rera_registration_id",
            "rera.rera_registration_id",
        ],
        "attributes.compliance.project_rera_registration_id": [
            "attributes.compliance.project_rera_registration_id",
            "project_rera_registration_id",
            "relationships.project.rera_registration_id",
        ],
        "attributes.tags_and_signals.property_tags": [
            "attributes.tags_and_signals.property_tags", "property_tags"
        ],
        "attributes.tags_and_signals.tags": [
            "attributes.tags_and_signals.tags", "tags"
        ],
        "attributes.tags_and_signals.top_usps": [
            "attributes.tags_and_signals.top_usps",
            "top_usps",
            "source_specific.top_usps",
        ],
    }.items():
        value = _first_value(source, paths)
        if value is not None:
            set_path(output, target, value)

    set_path(
        output, schema_config.get("amenities_target", "amenities"),
        amenities
    )

    # Custom field mappings override built-in mappings.
    for target_path, source_path in schema_config.get("field_map", {}).items():
        value = get_path(source, source_path)
        if value is not None:
            set_path(output, target_path, value)

    return output
def find_image_urls(node):
    """Find image URLs in common URL fields and image collections."""
    found = []
    url_keys = {
        "url", "src", "image_url", "imageurl", "original_url",
        "large_url", "full_url", "thumbnail_url", "image_src",
        "photo_url", "picture_url", "cdn_url",
    }
    image_context_words = (
        "image", "photo", "picture", "media",
        "gallery", "thumbnail", "thumb"
    )

    def walk(value, key="", image_context=False):
        key_lower = str(key).lower()
        current_image_context = image_context or any(
            word in key_lower for word in image_context_words
        )

        if isinstance(value, dict):
            for k, child in value.items():
                child_key = str(k).lower()
                is_url_field = (
                    child_key in url_keys
                    or child_key.endswith("_url")
                    or child_key.endswith("url")
                )
                if (
                    isinstance(child, str)
                    and child.startswith(("http://", "https://"))
                    and (
                        is_url_field
                        or current_image_context
                        or any(word in child_key for word in image_context_words)
                    )
                ):
                    found.append(child)
                else:
                    walk(child, k, current_image_context)

        elif isinstance(value, list):
            for child in value:
                if (
                    isinstance(child, str)
                    and child.startswith(("http://", "https://"))
                    and current_image_context
                ):
                    found.append(child)
                else:
                    walk(child, key, current_image_context)

        elif (
            isinstance(value, str)
            and value.startswith(("http://", "https://"))
            and current_image_context
        ):
            found.append(value)

    walk(node)
    return list(dict.fromkeys(found))


def is_safe_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False

    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        return False

    try:
        addresses = socket.getaddrinfo(host, None)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                return False
    except (socket.gaierror, ValueError):
        return False

    return True


def replace_exact(node, old, new):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, str) and value == old:
                node[key] = new
            else:
                replace_exact(value, old, new)
    elif isinstance(node, list):
        for item in node:
            replace_exact(item, old, new)
def migrate_images(
    listing,
    s3_client,
    bucket,
    prefix="migrated-listings",
    public_base_url=""
):
    warnings = []

    for image_url in find_image_urls(listing):
        try:
            if not is_safe_public_url(image_url):
                warnings.append(
                    f"सुरक्षा जाँच में URL skip किया गया: {image_url[:150]}"
                )
                continue

            response = requests.get(
                image_url,
                timeout=(10, 35),
                stream=True,
                headers={"User-Agent": "ListingMigrator/1.0"},
            )
            response.raise_for_status()

            content_type = (
                response.headers.get("Content-Type", "")
                .split(";")[0].strip().lower()
            )

            if not content_type.startswith("image/"):
                response.close()
                warnings.append(
                    f"URL से image content नहीं मिला: {image_url[:150]}"
                )
                continue

            body = response.content
            response.close()

            if not body or len(body) > 20 * 1024 * 1024:
                warnings.append(
                    f"खाली या 20 MB से बड़ी image skip हुई: {image_url[:150]}"
                )
                continue

            extension = (
                mimetypes.guess_extension(content_type)
                or os.path.splitext(urlparse(image_url).path)[1]
                or ".img"
            )
            digest = hashlib.sha256(
                image_url.encode("utf-8")
            ).hexdigest()[:20]
            key = f"{prefix.strip('/')}/{digest}{extension}"

            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={
                    "source-url-sha256": hashlib.sha256(
                        image_url.encode("utf-8")
                    ).hexdigest()
                },
            )

            if public_base_url:
                new_url = f"{public_base_url}/{key}"
            else:
                region = os.environ.get("AWS_REGION", "ap-south-1")
                new_url = (
                    f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
                )

            replace_exact(listing, image_url, new_url)

        except Exception as exc:
            warnings.append(
                f"Image migrate नहीं हुई ({image_url[:100]}): "
                f"{str(exc)[:160]}"
            )

    return listing, warnings
