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
    for key in ("amenities", "featu
