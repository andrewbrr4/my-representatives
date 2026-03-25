"""Google Civic Information API client for election data."""

import hashlib
import logging
import os

import httpx

from models import (
    Candidate,
    Contest,
    Election,
    ElectionsResponse,
    PollingLocation,
    VoterInfo,
)

logger = logging.getLogger(__name__)

_CIVIC_API_BASE = "https://www.googleapis.com/civicinfo/v2"

# Map Google Civic API office levels to our level values
_LEVEL_MAP = {
    "country": "federal",
    "administrativeArea1": "state",
    "administrativeArea2": "municipal",
    "locality": "municipal",
    "regional": "municipal",
    "special": "municipal",
    "subLocality1": "municipal",
    "subLocality2": "municipal",
}


def address_hash(address: str) -> str:
    """Deterministic short hash of an address for cache keys."""
    return hashlib.sha256(address.lower().strip().encode()).hexdigest()[:12]


async def fetch_elections(address: str) -> ElectionsResponse:
    """Fetch upcoming elections and ballot info for an address from Google Civic API."""
    api_key = os.environ.get("GOOGLE_CIVIC_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_CIVIC_API_KEY not set, returning empty elections")
        return ElectionsResponse(elections=[])

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_CIVIC_API_BASE}/voterinfo",
            params={"address": address, "key": api_key},
        )

        if resp.status_code == 400:
            # No elections upcoming for this address
            logger.info(f"No elections found for address (400 response)")
            return ElectionsResponse(elections=[])

        resp.raise_for_status()
        data = resp.json()

    return _parse_civic_response(data)


def _parse_civic_response(data: dict) -> ElectionsResponse:
    """Parse the Google Civic API voterinfo response into our models."""
    election_data = data.get("election", {})
    if not election_data or election_data.get("id") == "0":
        return ElectionsResponse(elections=[])

    # Parse polling location
    polling_location = None
    polling_locations = data.get("pollingLocations", [])
    if polling_locations:
        pl = polling_locations[0]
        addr = pl.get("address", {})
        polling_location = PollingLocation(
            name=addr.get("locationName", "Polling Location"),
            address=_format_civic_address(addr),
            hours=pl.get("pollingHours"),
        )

    # Parse contests and candidates
    contests = []
    for contest_data in data.get("contests", []):
        office = contest_data.get("office", "Unknown Office")
        level = "municipal"  # default
        levels = contest_data.get("level", [])
        if levels:
            level = _LEVEL_MAP.get(levels[0], "municipal")

        district = contest_data.get("district", {})
        district_name = district.get("name")

        candidates = []
        for cand_data in contest_data.get("candidates", []):
            candidates.append(Candidate(
                name=cand_data.get("name", "Unknown"),
                office=office,
                level=level,
                party=cand_data.get("party"),
                photo_url=cand_data.get("photoUrl"),
                contest_name=f"{office} - {district_name}" if district_name else office,
                incumbent=False,  # Civic API doesn't reliably indicate this
            ))

        contests.append(Contest(
            office=office,
            level=level,
            district_name=district_name,
            candidates=candidates,
        ))

    # Parse voter info from state administration body
    voter_info = _parse_voter_info(data)

    # Parse early vote sites and drop-off locations into voter_info
    for site in data.get("earlyVoteSites", []):
        addr = site.get("address", {})
        voter_info.early_vote_sites.append(PollingLocation(
            name=addr.get("locationName", "Early Vote Site"),
            address=_format_civic_address(addr),
            hours=site.get("pollingHours"),
        ))
    for loc in data.get("dropOffLocations", []):
        addr = loc.get("address", {})
        voter_info.drop_off_locations.append(PollingLocation(
            name=addr.get("locationName", "Drop-off Location"),
            address=_format_civic_address(addr),
            hours=loc.get("pollingHours"),
        ))

    # Determine election type from name
    election_name = election_data.get("name", "Unknown Election")
    election_type = _infer_election_type(election_name)

    election = Election(
        name=election_name,
        date=election_data.get("electionDay", ""),
        election_type=election_type,
        polling_location=polling_location,
        voter_info=voter_info,
        contests=contests,
    )

    return ElectionsResponse(elections=[election])


def _parse_voter_info(data: dict) -> VoterInfo:
    """Extract voter info from Civic API state[].electionAdministrationBody."""
    states = data.get("state", [])
    if not states:
        return VoterInfo()

    admin = states[0].get("electionAdministrationBody", {})
    if not admin:
        return VoterInfo()

    return VoterInfo(
        registration_url=admin.get("electionRegistrationUrl"),
        absentee_url=admin.get("absenteeVotingInfoUrl"),
        ballot_info_url=admin.get("ballotInfoUrl"),
        polling_location_url=admin.get("votingLocationFinderUrl"),
        mail_only=data.get("mailOnly", False),
        admin_body_name=admin.get("name"),
        admin_body_url=admin.get("electionInfoUrl"),
    )


def _format_civic_address(addr: dict) -> str:
    """Format a Civic API address object into a single string."""
    parts = [
        addr.get("line1", ""),
        addr.get("line2", ""),
        addr.get("city", ""),
        addr.get("state", ""),
        addr.get("zip", ""),
    ]
    return ", ".join(p for p in parts if p)


def _infer_election_type(name: str) -> str:
    """Guess election type from the election name."""
    lower = name.lower()
    if "runoff" in lower:
        return "runoff"
    if "primary" in lower:
        return "primary"
    if "general" in lower:
        return "general"
    return "general"  # default
