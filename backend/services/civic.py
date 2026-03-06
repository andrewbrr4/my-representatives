import logging
import os

import httpx

from models import Contact, Representative

logger = logging.getLogger(__name__)

CICERO_API_URL = "https://app.cicerodata.com/v3.1/official"

DISTRICT_TYPE_TO_LEVEL = {
    "NATIONAL_EXEC": "federal",
    "NATIONAL_UPPER": "federal",
    "NATIONAL_LOWER": "federal",
    "STATE_EXEC": "state",
    "STATE_UPPER": "state",
    "STATE_LOWER": "state",
    "LOCAL_EXEC": "municipal",
    "LOCAL": "municipal",
}


async def get_representatives(address: str) -> list[Representative]:
    api_key = os.environ["CICERO_API_KEY"]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            CICERO_API_URL,
            params={
                "key": api_key,
                "search_loc": address,
                "format": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("response", {}).get("results", {}).get("candidates", [])
    if not candidates:
        return []

    officials = candidates[0].get("officials", [])
    representatives: list[Representative] = []

    for official in officials:
        office = official.get("office", {})
        district = office.get("district", {})
        district_type = district.get("district_type", "")
        chamber = office.get("chamber", {})

        first = official.get("first_name", "")
        last = official.get("last_name", "")
        name = f"{first} {last}".strip() or "Unknown"

        logger.info(f"Official: {name}, district_type={district_type}, is_appointed={chamber.get('is_appointed')}, office={office.get('title')}")

        # Skip appointed officials (cabinet members, etc.)
        if chamber.get("is_appointed"):
            logger.info(f"Skipping {name} (appointed)")
            continue

        level = DISTRICT_TYPE_TO_LEVEL.get(district_type, "municipal")

        party = official.get("party")

        photo_url = official.get("photo_origin_url")

        # Extract contact info
        addresses = official.get("addresses", [])
        phone = None
        if addresses:
            phone = addresses[0].get("phone_1")

        emails = official.get("email_addresses", [])
        email = emails[0] if emails else None

        urls = official.get("urls", [])
        website = urls[0] if urls else None

        office_title = office.get("title", "Unknown Office")

        contact = Contact(
            website=website,
            phone=phone,
            email=email,
        )

        representatives.append(
            Representative(
                name=name,
                office=office_title,
                level=level,
                party=party,
                photo_url=photo_url,
                contact=contact,
            )
        )

    logger.info(f"Cicero API returned {len(representatives)} elected officials")
    return representatives
