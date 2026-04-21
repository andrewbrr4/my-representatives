"""Tests for v2 dossier builder and citation renumbering."""

from models import Citation
from research.overview.v2.synthesis_input import build_dossier


def test_build_dossier_empty_sections():
    result = build_dossier([])
    assert result.dossier == ""
    assert result.unified_citations == []


def test_build_dossier_single_section():
    sections = [
        (
            "policy_positions",
            ["**Climate** - Supports the clean grid bill. [1]", "**Taxes** - Opposes the 2024 cut. [2]"],
            [
                Citation(title="NYT", url="https://nyt.example/a"),
                Citation(title="WSJ", url="https://wsj.example/b"),
            ],
        ),
    ]
    result = build_dossier(sections)

    assert "## policy_positions" in result.dossier
    assert "**Climate** - Supports the clean grid bill. [1]" in result.dossier
    assert "Sources:" in result.dossier
    assert "[1] https://nyt.example/a" in result.dossier
    assert "[2] https://wsj.example/b" in result.dossier
    assert len(result.unified_citations) == 2
    assert result.unified_citations[0].url == "https://nyt.example/a"


def test_build_dossier_renumbers_across_sections():
    """Two sections with [1]/[2] each — after merging, the second section's
    markers should be rewritten to [3]/[4]."""
    sections = [
        (
            "policy_positions",
            ["**A** - First. [1]", "**B** - Second. [2]"],
            [
                Citation(title="S1", url="https://s1.example"),
                Citation(title="S2", url="https://s2.example"),
            ],
        ),
        (
            "controversies",
            ["**C** - Third. [1]", "**D** - Fourth. [2]"],
            [
                Citation(title="S3", url="https://s3.example"),
                Citation(title="S4", url="https://s4.example"),
            ],
        ),
    ]
    result = build_dossier(sections)
    assert "**C** - Third. [3]" in result.dossier
    assert "**D** - Fourth. [4]" in result.dossier
    assert [c.url for c in result.unified_citations] == [
        "https://s1.example",
        "https://s2.example",
        "https://s3.example",
        "https://s4.example",
    ]


def test_build_dossier_skips_sections_with_empty_content():
    sections = [
        ("policy_positions", [], []),
        (
            "controversies",
            ["**X** - only. [1]"],
            [Citation(title="S1", url="https://s1.example")],
        ),
    ]
    result = build_dossier(sections)
    assert "## policy_positions" not in result.dossier
    assert "**X** - only. [1]" in result.dossier
    assert len(result.unified_citations) == 1
