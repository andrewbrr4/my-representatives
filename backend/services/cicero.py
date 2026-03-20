import logging
import os

import httpx

from models import Contact, Representative

logger = logging.getLogger(__name__)

CICERO_API_URL = "https://app.cicerodata.com/v3.1/official"
WHITEHOUSE_ADDRESS = "1600 Pennsylvania Avenue NW, Washington, DC 20500"

DISTRICT_TYPE_TO_LEVEL = {
    "NATIONAL_EXEC": "federal",
    "STATE_EXEC": "state",
    "STATE_UPPER": "state",
    "STATE_LOWER": "state",
    "LOCAL_EXEC": "municipal",
    "LOCAL": "municipal",
}

PRESIDENT_VP_OFFICES = {"President", "Vice President"}


async def _fetch_officials(client: httpx.AsyncClient, api_key: str, address: str) -> list[dict]:
    """Fetch raw officials list from Cicero for an address."""
    resp = await client.get(
        CICERO_API_URL,
        params={"key": api_key, "search_loc": address, "format": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("response", {}).get("results", {}).get("candidates", [])
    if not candidates:
        return []
    return candidates[0].get("officials", [])


def _parse_officials(officials: list[dict], skip_federal_legislators: bool = True) -> list[Representative]:
    """Parse Cicero officials into Representative models."""
    representatives: list[Representative] = []

    for official in officials:
        office = official.get("office", {})
        district = office.get("district", {})
        district_type = district.get("district_type", "")
        chamber = office.get("chamber", {})

        first = official.get("first_name", "")
        last = official.get("last_name", "")
        name = f"{first} {last}".strip() or "Unknown"

        logger.info(
            f"Official: {name}, district_type={district_type}, "
            f"is_appointed={chamber.get('is_appointed')}, office={office.get('title')}"
        )

        if chamber.get("is_appointed"):
            logger.info(f"Skipping {name} (appointed)")
            continue

        if skip_federal_legislators and district_type in ("NATIONAL_UPPER", "NATIONAL_LOWER"):
            logger.info(f"Skipping {name} (federal legislator, handled by Congress API)")
            continue

        level = DISTRICT_TYPE_TO_LEVEL.get(district_type, "municipal")
        party = official.get("party")
        photo_url = official.get("photo_origin_url")

        addresses = official.get("addresses", [])
        phone = addresses[0].get("phone_1") if addresses else None

        emails = official.get("email_addresses", [])
        email = emails[0] if emails else None

        urls = official.get("urls", [])
        website = urls[0] if urls else None

        office_title = office.get("title", "Unknown Office")

        representatives.append(
            Representative(
                name=name,
                office=office_title,
                level=level,
                party=party,
                photo_url=photo_url,
                contact=Contact(website=website, phone=phone, email=email),
            )
        )

    return representatives


async def get_state_local_representatives(address: str) -> list[Representative]:
    """Get state, municipal, and executive representatives from Cicero.

    Cicero inconsistently returns President/VP depending on the address.
    When missing, a fallback lookup using the White House address fills the gap.
    """
    api_key = os.environ["CICERO_API_KEY"]

    async with httpx.AsyncClient() as client:
        officials = await _fetch_officials(client, api_key, address)
        reps = _parse_officials(officials)

        # Check if President/VP are present
        existing_offices = {r.office for r in reps}
        missing = PRESIDENT_VP_OFFICES - existing_offices

        if missing:
            logger.info(f"Missing {missing} from Cicero response, fetching via White House address")
            fallback_officials = await _fetch_officials(client, api_key, WHITEHOUSE_ADDRESS)
            fallback_reps = _parse_officials(fallback_officials)
            for rep in fallback_reps:
                if rep.office in missing:
                    reps.append(rep)

    logger.info(f"Cicero returned {len(reps)} elected officials")
    return reps
