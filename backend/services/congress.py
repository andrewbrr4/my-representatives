import logging
import os

import httpx

from models import Contact, Representative

logger = logging.getLogger(__name__)

CONGRESS_API_URL = "https://api.congress.gov/v3"
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"

CURRENT_CONGRESS = 119


async def _geocode_address(client: httpx.AsyncClient, address: str) -> dict:
    """Use Census geocoder to get state and congressional district from address."""
    resp = await client.get(
        CENSUS_GEOCODER_URL,
        params={
            "address": address,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        raise ValueError("Census geocoder could not match the address")

    match = matches[0]
    geos = match.get("geographies", {})

    states = geos.get("States", [])
    if not states:
        raise ValueError("No state found for address")
    state_abbr = states[0].get("STUSAB")

    cd_key = f"{CURRENT_CONGRESS}th Congressional Districts"
    districts = geos.get(cd_key, [])
    if not districts:
        raise ValueError("No congressional district found for address")
    district_num = districts[0].get(f"CD{CURRENT_CONGRESS}")

    return {"state": state_abbr, "district": district_num}


def _member_to_representative(member: dict) -> Representative:
    """Convert a Congress API member detail to a Representative model."""
    first = member.get("firstName", "")
    last = member.get("lastName", "")
    name = member.get("directOrderName") or f"{first} {last}".strip() or "Unknown"

    terms = member.get("terms", [])
    office = "Member of Congress"
    if terms:
        latest = terms[-1]
        chamber = latest.get("chamber", "")
        if chamber == "Senate":
            office = f"U.S. Senator, {member.get('state', '')}"
        else:
            district = latest.get("district")
            state = latest.get("stateName", member.get("state", ""))
            office = f"U.S. Representative, {state} District {district}"

    party = None
    party_history = member.get("partyHistory", [])
    if party_history:
        party = party_history[-1].get("partyName")

    photo_url = None
    depiction = member.get("depiction")
    if depiction:
        photo_url = depiction.get("imageUrl")

    addr_info = member.get("addressInformation", {})
    phone = addr_info.get("phoneNumber")
    website = member.get("officialWebsiteUrl")

    return Representative(
        name=name,
        office=office,
        level="federal",
        party=party,
        photo_url=photo_url,
        contact=Contact(website=website, phone=phone),
    )


async def get_federal_representatives(address: str) -> list[Representative]:
    """Look up federal representatives using Census geocoder + Congress API."""
    api_key = os.environ["US_CONGRESS_API_KEY"]

    async with httpx.AsyncClient() as client:
        geo = await _geocode_address(client, address)
        state = geo["state"]
        district = geo["district"]

        logger.info(f"Geocoded to state={state}, district={district}")

        resp = await client.get(
            f"{CONGRESS_API_URL}/member/congress/{CURRENT_CONGRESS}/{state}",
            params={"api_key": api_key, "format": "json", "limit": 50},
            timeout=15,
        )
        resp.raise_for_status()
        all_members = resp.json().get("members", [])

        # Filter to senators (district=None) and the matching House district
        relevant = []
        for m in all_members:
            m_district = m.get("district")
            if m_district is None:
                relevant.append(m)
            elif int(m_district) == int(district):
                relevant.append(m)

        logger.info(f"Found {len(relevant)} federal reps for {state}-{district}")

        # Fetch full details for each relevant member
        representatives = []
        for m in relevant:
            try:
                url = m["url"]
                if not url.startswith("http"):
                    url = f"{CONGRESS_API_URL}{url}"
                detail_resp = await client.get(
                    url, params={"api_key": api_key, "format": "json"}, timeout=15
                )
                detail_resp.raise_for_status()
                detail = detail_resp.json().get("member", {})
                representatives.append(_member_to_representative(detail))
            except Exception as e:
                logger.warning(f"Failed to fetch detail for {m.get('name')}: {e}")
                # Fall back to list-level data (less info but still usable)
                representatives.append(_member_to_representative(m))

    return representatives
