import asyncio
import logging
import os

import httpx

from models import Contact, Representative

logger = logging.getLogger(__name__)

CONGRESS_API_URL = "https://api.congress.gov/v3"
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"

CURRENT_CONGRESS = 119

_GEOCODER_MAX_ATTEMPTS = 4
_GEOCODER_BASE_DELAY = 0.5  # seconds; doubles each retry → 0.5, 1, 2, 4


async def _geocode_address(client: httpx.AsyncClient, address: str) -> dict:
    """Use Census geocoder to get state and congressional district from address.

    Census Geocoder is a free service that returns transient 5xx and timeouts
    under load. Retry with exponential backoff before surfacing the error.
    """
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }

    last_exc: Exception | None = None
    for attempt in range(_GEOCODER_MAX_ATTEMPTS):
        try:
            resp = await client.get(CENSUS_GEOCODER_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            break
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError) as e:
            # Retry only on transient errors: 5xx, timeouts, network blips.
            # 4xx (bad address) should fail fast.
            status = getattr(getattr(e, "response", None), "status_code", None)
            is_transient = (
                isinstance(e, (httpx.TimeoutException, httpx.TransportError))
                or (status is not None and 500 <= status < 600)
            )
            if not is_transient or attempt == _GEOCODER_MAX_ATTEMPTS - 1:
                raise
            delay = _GEOCODER_BASE_DELAY * (2**attempt)
            logger.warning(
                f"Census geocoder transient error ({type(e).__name__}, status={status}); "
                f"retrying in {delay}s (attempt {attempt + 1}/{_GEOCODER_MAX_ATTEMPTS})"
            )
            last_exc = e
            await asyncio.sleep(delay)
    else:  # pragma: no cover — defensive; loop always breaks or raises
        raise last_exc or RuntimeError("Census geocoder failed without exception")

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


async def get_federal_representatives(address: str) -> tuple[list[Representative], dict]:
    """Look up federal representatives using Census geocoder + Congress API.

    Returns ``(reps, geo)`` where ``geo`` is ``{"state": str, "district": str}``
    so callers can also surface the user's congressional district.
    """
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

        # Filter to senators (district=None) and the matching House district.
        # Skip members whose latest term has an endYear — the API still lists
        # members who served in this congress but have since left (e.g. Rubio,
        # confirmed as Secretary of State, has endYear=2025 on his only term).
        relevant = []
        for m in all_members:
            term_items = m.get("terms", {}).get("item", [])
            if term_items and term_items[-1].get("endYear") is not None:
                logger.info(
                    f"Skipping {m.get('name')} (term ended {term_items[-1].get('endYear')})"
                )
                continue

            m_district = m.get("district")
            if m_district is None:
                relevant.append(m)
            elif int(m_district) == int(district):
                relevant.append(m)

        logger.info(f"Found {len(relevant)} federal reps for {state}-{district}")

        # Fetch full details for each relevant member (concurrently)
        async def _fetch_detail(m: dict) -> Representative:
            try:
                url = m["url"]
                if not url.startswith("http"):
                    url = f"{CONGRESS_API_URL}{url}"
                detail_resp = await client.get(
                    url, params={"api_key": api_key, "format": "json"}, timeout=15
                )
                detail_resp.raise_for_status()
                detail = detail_resp.json().get("member", {})
                return _member_to_representative(detail)
            except Exception as e:
                logger.warning(f"Failed to fetch detail for {m.get('name')}: {e}")
                # Fall back to list-level data (less info but still usable)
                return _member_to_representative(m)

        representatives = list(await asyncio.gather(*[_fetch_detail(m) for m in relevant]))

    return representatives, geo
