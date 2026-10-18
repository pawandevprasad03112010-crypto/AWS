
# Amenities Detection Guide

This project detects amenities using keyword matching.
It does not require an AI API.

## How It Works

The application scans listing text for known amenity keywords
and adds matching amenities to the output JSON.

## Supported Amenities

- Swimming Pool
- Gymnasium
- Clubhouse
- Children's Play Area
- Garden
- Parking
- Power Backup
- Lift
- Security
- CCTV
- Indoor Games
- Sports Facilities
- Jogging Track
- Yoga Room
- Multipurpose Hall
- Rainwater Harvesting
- Sewage Treatment Plant
- Fire Safety
- Visitor Parking
- Maintenance Staff

## Important Notes

- Detection depends on keywords defined in `transformer.py`.
- A keyword match does not guarantee that an amenity is available.
- Review the output JSON before using it in production.
- Add more keywords to `AMENITY_PATTERNS` in `transformer.py`
  when additional amenities need to be detected.
- The output field is configured through `amenities_target`
  in `schema_template.json`.
  
