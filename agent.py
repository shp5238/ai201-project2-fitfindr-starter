"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    # ── Step 2: Parse query ───────────────────────────────────────────────────
    # Extract max_price: "under $30", "$30", "under 30"
    price_match = re.search(r"(?:under\s*)?\$(\d+(?:\.\d+)?)|under\s+(\d+(?:\.\d+)?)", query, re.I)
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)

    # Extract size: "size M", "in XS", or standalone token matching common sizes
    size_match = re.search(
        r"\bsize\s+([A-Z0-9/]+)\b"
        r"|\bin\s+(XXS|XS|S|M|L|XL|XXL|XXXL|[0-9]+(?:\.[05])?)\b"
        r"|\b(XXS|XS|XL|XXL|XXXL)\b",  # unambiguous standalone tokens only
        query,
        re.I,
    )
    size = None
    if size_match:
        size = next(g for g in size_match.groups() if g is not None)

    # Description: strip price/size tokens to get clean keyword string
    description = query
    if price_match:
        description = description[:price_match.start()] + description[price_match.end():]
    if size_match:
        description = description[:size_match.start()] + description[size_match.end():]
    description = re.sub(r"\b(size|in|under|looking for|i want|find me|a|an|the)\b", " ", description, flags=re.I)
    description = " ".join(description.split())

    session["parsed"] = {"description": description, "size": size, "max_price": max_price}

    # ── Step 3: Search ────────────────────────────────────────────────────────
    results = search_listings(description, size=size, max_price=max_price)
    session["search_results"] = results

    if not results:
        size_str = f" in size {size}" if size else ""
        price_str = f" under ${max_price:.0f}" if max_price else ""
        session["error"] = (
            f"No listings found for '{description}'{size_str}{price_str}. "
            "Try broadening your search — remove the size filter or raise your budget."
        )
        return session

    # ── Step 4: Select top result ─────────────────────────────────────────────
    session["selected_item"] = results[0]

    # ── Step 5: Suggest outfit ────────────────────────────────────────────────
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    # ── Step 6: Create fit card ───────────────────────────────────────────────
    session["fit_card"] = create_fit_card(outfit, session["selected_item"])

    # ── Step 7: Return ────────────────────────────────────────────────────────
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
