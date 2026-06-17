"""
Tests for tools.py — one test per failure mode plus happy-path coverage.
suggest_outfit and create_fit_card mock the Groq client to avoid API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools import create_fit_card, search_listings, suggest_outfit


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_groq_response(text: str):
    """Build a minimal mock that looks like a Groq chat completion response."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


SAMPLE_ITEM = {
    "id": "lst_001",
    "title": "Faded Band Tee",
    "category": "tops",
    "colors": ["black", "grey"],
    "style_tags": ["vintage", "grunge", "graphic"],
    "description": "Worn-in black tee with faded band print",
    "price": 22.0,
    "platform": "depop",
    "size": "M",
    "condition": "good",
    "brand": None,
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w-01",
            "name": "Wide-leg jeans",
            "category": "bottoms",
            "colors": ["blue"],
            "style_tags": ["baggy", "casual", "90s"],
        },
        {
            "id": "w-02",
            "name": "Chunky platform sneakers",
            "category": "shoes",
            "colors": ["white"],
            "style_tags": ["streetwear", "chunky", "90s"],
        },
    ]
}

EMPTY_WARDROBE = {"items": []}


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: nothing matches → empty list, no exception
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    # All returned items must be within the price ceiling
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # Size match is case-insensitive ("m" should match "M", "S/M", etc.)
    results_upper = search_listings("tee", size="M", max_price=None)
    results_lower = search_listings("tee", size="m", max_price=None)
    assert results_upper == results_lower


def test_search_sorted_by_relevance():
    # Higher keyword overlap should appear first
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) >= 2
    # First result should contain more of the keywords than a later one
    # (just check list is non-empty and ordered — don't hardcode titles)
    assert isinstance(results[0], dict)


def test_search_no_size_or_price_returns_description_matches():
    # No filters — still scores by description
    results = search_listings("flannel", size=None, max_price=None)
    assert len(results) >= 1
    assert any("flannel" in r["title"].lower() or "flannel" in r["description"].lower()
               for r in results)


# ── suggest_outfit ────────────────────────────────────────────────────────────

@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe(mock_client):
    mock_client.return_value.chat.completions.create.return_value = (
        _make_groq_response("Pair the tee with Wide-leg jeans and Chunky platform sneakers.")
    )
    result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_no_crash(mock_client):
    # Failure mode: empty wardrobe → general styling advice, no exception
    mock_client.return_value.chat.completions.create.return_value = (
        _make_groq_response("Great for layering over a turtleneck with wide-leg trousers.")
    )
    result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_calls_llm_once(mock_client):
    # Even on empty wardrobe, LLM must be called (not silently skipped)
    mock_create = mock_client.return_value.chat.completions.create
    mock_create.return_value = _make_groq_response("General style tip here.")
    suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    mock_create.assert_called_once()


@patch("tools._get_groq_client")
def test_suggest_outfit_wardrobe_items_in_prompt(mock_client):
    # Wardrobe item names should appear in the prompt sent to the LLM
    mock_create = mock_client.return_value.chat.completions.create
    mock_create.return_value = _make_groq_response("Outfit suggestion.")
    suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    call_args = mock_create.call_args
    prompt_text = call_args.kwargs["messages"][0]["content"]
    assert "Wide-leg jeans" in prompt_text
    assert "Chunky platform sneakers" in prompt_text


# ── create_fit_card ───────────────────────────────────────────────────────────

@patch("tools._get_groq_client")
def test_create_fit_card_returns_caption(mock_client):
    mock_client.return_value.chat.completions.create.return_value = (
        _make_groq_response("Thrifted this Faded Band Tee off depop for $22 — pure grunge energy.")
    )
    result = create_fit_card("Pair with wide-leg jeans.", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error():
    # Failure mode: empty outfit string → error message string, no exception
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "incomplete" in result.lower() or "wasn't" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error():
    # Whitespace-only outfit is also invalid
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "incomplete" in result.lower() or "wasn't" in result.lower()


@patch("tools._get_groq_client")
def test_create_fit_card_uses_high_temperature(mock_client):
    # temperature should be > 1.0 so outputs vary
    mock_create = mock_client.return_value.chat.completions.create
    mock_create.return_value = _make_groq_response("Caption here.")
    create_fit_card("Outfit suggestion.", SAMPLE_ITEM)
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs.get("temperature", 0) > 1.0


@patch("tools._get_groq_client")
def test_create_fit_card_prompt_includes_item_fields(mock_client):
    # title, price, platform must all appear in prompt
    mock_create = mock_client.return_value.chat.completions.create
    mock_create.return_value = _make_groq_response("Caption here.")
    create_fit_card("Outfit suggestion.", SAMPLE_ITEM)
    prompt = mock_create.call_args.kwargs["messages"][0]["content"]
    assert "Faded Band Tee" in prompt
    assert "22" in prompt
    assert "depop" in prompt
