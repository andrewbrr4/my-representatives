import os

import httpx

from models import Contact, Representative

CIVIC_API_URL = "https://www.googleapis.com/civicinfo/v2/representatives"

LEVEL_MAP = {
    "country": "federal",
    "administrativeArea1": "state",
    "administrativeArea2": "municipal",
    "locality": "municipal",
    "regional": "state",
    "special": "municipal",
    "subLocality1": "municipal",
    "subLocality2": "municipal",
}


async def get_representatives(address: str) -> list[Representative]:
    api_key = os.environ["GOOGLE_CIVIC_API_KEY"]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            CIVIC_API_URL,
            params={"key": api_key, "address": address},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    offices = data.get("offices", [])
    officials = data.get("officials", [])

    representatives: list[Representative] = []

    for office in offices:
        levels = office.get("levels", [])
        level = "federal"
        for lv in levels:
            if lv in LEVEL_MAP:
                level = LEVEL_MAP[lv]
                break

        for idx in office.get("officialIndices", []):
            if idx >= len(officials):
                continue
            official = officials[idx]

            channels = {
                ch["type"].lower(): ch["id"]
                for ch in official.get("channels", [])
            }

            urls = official.get("urls", [])
            phones = official.get("phones", [])
            emails = official.get("emails", [])

            contact = Contact(
                website=urls[0] if urls else None,
                phone=phones[0] if phones else None,
                email=emails[0] if emails else None,
            )

            representatives.append(
                Representative(
                    name=official.get("name", "Unknown"),
                    office=office.get("name", "Unknown Office"),
                    level=level,
                    party=official.get("party"),
                    photo_url=official.get("photoUrl"),
                    contact=contact,
                )
            )

    return representatives
