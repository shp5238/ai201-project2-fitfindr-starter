# FitFindr

FitFindr is an AI-powered thrift shopping assistant. You give it a natural language query like "vintage graphic tee under $30, size M" and it searches a mock secondhand marketplace, picks the best match, builds an outfit using your existing wardrobe, and generates a shareable Instagram/TikTok caption — all in one shot.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file with your Groq key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the agent:

```bash
python agent.py
```

Run tests:

```bash
pytest tests/test_tools.py -v
```

---

## Project Structure

```
AIp2/
├── agent.py           # planning loop + run_agent()
├── tools.py           # the three tools
├── app.py             # Gradio UI — runs on localhost:7860
├── tests/
│   └── test_tools.py  # unit tests for all three tools
├── utils/
│   └── data_loader.py # load_listings(), get_example_wardrobe()
├── data/
│   ├── listings.json         # 40 mock secondhand listings
│   └── wardrobe_schema.json  # wardrobe format + example
└── planning.md        # design doc written before any code
```

---

## Tool Inventory

### Tool 1: `search_listings`

**Purpose:** Searches the mock thrift marketplace dataset and returns listings that match the user's description, size, and price ceiling. This is always the first tool called — it's how the agent figures out what's actually available before trying to style anything.

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords describing what the user wants, e.g. `"vintage graphic tee"`. Matched against title, description, and style_tags. |
| `size` | `str \| None` | Size to filter by, e.g. `"M"`. Matching is case-insensitive. Pass `None` to skip size filtering. |
| `max_price` | `float \| None` | Price ceiling (inclusive). Pass `None` to skip price filtering. |

**Output:** `list[dict]` — a list of matching listing dictionaries sorted by relevance (most keyword overlap first). Each dict has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never raises an exception.

---

### Tool 2: `suggest_outfit`

**Purpose:** Takes the thrifted item the user is considering and their existing wardrobe, then asks an LLM (Llama 3.3 via Groq) to suggest 1–2 complete outfit combinations. If the wardrobe is empty it still works — it just gives general styling advice for the item instead.

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict (the top result from `search_listings`). Must have `title`, `category`, `colors`, `style_tags`, `description`. |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key. Each item has `name`, `category`, `colors`, `style_tags`. Can be empty — the tool handles that gracefully. |

**Output:** `str` — a non-empty string with outfit suggestions. If wardrobe is populated, it references specific piece names from the wardrobe. If wardrobe is empty, it offers general styling guidance.

---

### Tool 3: `create_fit_card`

**Purpose:** Takes the outfit suggestion and the item details and generates a 2–4 sentence caption you could actually post on Instagram or TikTok. It uses a higher LLM temperature (1.2) so the captions sound different each time and don't feel like a template.

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string returned by `suggest_outfit`. |
| `new_item` | `dict` | The listing dict for the thrifted item. Must have `title`, `price`, `platform`. |

**Output:** `str` — a 2–4 sentence caption string that mentions the item name, price, and platform naturally (once each) and captures the outfit vibe. If `outfit` is empty or whitespace-only, returns an error message string instead of raising an exception.

---

## Planning Loop

The planning loop lives in `run_agent()` in [agent.py](agent.py). Here's exactly how it works:

**Step 1 — Parse the query.**
The loop uses regex to pull out `max_price` (catches patterns like `"under $30"`, `"$30"`, `"under 30"`) and `size` (catches `"size M"`, `"in XL"`, and standalone tokens like `"XXL"`). Everything leftover after stripping those tokens becomes the `description`. This all gets stored in `session["parsed"]`.

**Step 2 — Call `search_listings(description, size, max_price)`.**
If results come back empty → set `session["error"]` with a helpful message telling the user to broaden their search, then **return early** without calling anything else. If results exist → store them in `session["search_results"]` and put `results[0]` in `session["selected_item"]`.

**Step 3 — Call `suggest_outfit(selected_item, wardrobe)`.**
The tool always returns a non-empty string (it handles empty wardrobes itself), so the loop stores the result in `session["outfit_suggestion"]` and moves on.

**Step 4 — Call `create_fit_card(outfit_suggestion, selected_item)`.**
Store the result in `session["fit_card"]`.

**Step 5 — Return the session dict.**
Caller checks `session["error"]` first. If it's `None`, all three output fields are populated.

The loop is strictly sequential — each step feeds into the next. There's only one branch point: empty search results trigger an early return. Everything else always runs to completion.

---

## State Management

All state for one interaction lives in a single `session` dict, created fresh by `_new_session(query, wardrobe)` at the start of every `run_agent()` call. The dict has these fields:

```python
{
    "query":             str,   # original user input
    "parsed":            dict,  # {"description": str, "size": str|None, "max_price": float|None}
    "search_results":    list,  # full results from search_listings()
    "selected_item":     dict,  # results[0] — the top match
    "wardrobe":          dict,  # user's wardrobe, unchanged throughout
    "outfit_suggestion": str,   # string from suggest_outfit()
    "fit_card":          str,   # string from create_fit_card()
    "error":             str,   # set only if interaction ends early
}
```

State flows one direction only: each tool writes its output into `session`, and the next tool reads from `session` to get its inputs. Nothing is re-computed or re-fetched. The session is the single source of truth — if you want to debug a run, you can print the whole dict and trace exactly what happened at each step.

`wardrobe` is passed in from the caller and stored in the session at initialization — it's never modified.

---

## Error Handling

### `search_listings` — no results

**Failure mode:** The description, size, and price filters together eliminate all 40 listings, so the function returns `[]`.

**What the agent does:** Sets `session["error"]` to a specific message that names what was searched for and suggests how to fix it, then returns immediately without calling `suggest_outfit` or `create_fit_card`.

**Concrete test example ([test_tools.py:71-73](tests/test_tools.py#L71-L73)):**
```python
def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []
```
Query `"designer ballgown"` with `size="XXS"` and `max_price=5` matches zero listings in the dataset. The function returns `[]` — no exception, no crash. The planning loop catches this, sets the error message `"No listings found for 'designer ballgown' in size XXS under $5. Try broadening your search — remove the size filter or raise your budget."`, and exits early.

---

### `suggest_outfit` — empty wardrobe

**Failure mode:** `wardrobe["items"]` is an empty list, so there are no pieces to reference in an outfit.

**What the agent does:** `suggest_outfit` handles this itself by detecting the empty wardrobe and switches to a different LLM prompt asking for general styling ideas instead of specific outfit combinations. It never raises an exception and never returns an empty string.

**Concrete test example ([test_tools.py:118-126](tests/test_tools.py#L118-L126)):**
```python
@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_no_crash(mock_client):
    mock_client.return_value.chat.completions.create.return_value = (
        _make_groq_response("Great for layering over a turtleneck with wide-leg trousers.")
    )
    result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0
```
Even with `EMPTY_WARDROBE = {"items": []}`, the function returns a non-empty string. There's also a companion test ([test_tools.py:130-135](tests/test_tools.py#L130-L135)) that verifies the LLM is actually called once (not silently skipped).

---

### `create_fit_card` — missing outfit input

**Failure mode:** `outfit` is an empty string or whitespace only, meaning `suggest_outfit` either wasn't called or returned nothing useful.

**What the agent does:** `create_fit_card` guards against this before touching the Groq client. If `not outfit or not outfit.strip()` is true, it returns the error string `"I wasn't able to generate a fit card because the outfit or item data is incomplete. Make sure your search and styling steps completed successfully."` — no API call, no exception.

**Concrete test examples ([test_tools.py:162-174](tests/test_tools.py#L162-L174)):**
```python
def test_create_fit_card_empty_outfit_returns_error():
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "incomplete" in result.lower() or "wasn't" in result.lower()

def test_create_fit_card_whitespace_outfit_returns_error():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "incomplete" in result.lower() or "wasn't" in result.lower()
```
Both an empty string and a whitespace-only string hit the guard and return the error message without any API call.

---

## Interaction Walkthrough

**User query:** `"looking for a vintage graphic tee under $30"`

**Step 1 — `search_listings` is called**
- **Tool:** `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`
- **Why this tool:** It's always first — need to find what's actually in the dataset before styling anything.
- **Output:** List of matching listings. Top result: `{"title": "Faded Band Tee", "price": 22.0, "platform": "depop", "size": "M", "style_tags": ["vintage", "grunge", "graphic"], ...}`
- Planning loop sets `session["selected_item"] = results[0]`.

**Step 2 — `suggest_outfit` is called**
- **Tool:** `suggest_outfit(new_item=session["selected_item"], wardrobe=example_wardrobe)`
- **Why this tool:** We have the item, now we need to figure out how to actually wear it.
- **Output:** `"Pair this faded band tee with your Wide-leg jeans and Chunky platform sneakers for a full 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape."`
- Planning loop stores this in `session["outfit_suggestion"]`.

**Step 3 — `create_fit_card` is called**
- **Tool:** `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`
- **Why this tool:** Last step — turn the outfit suggestion into something shareable.
- **Output:** `"Thrifted this Faded Band Tee off depop for $22 — paired it with wide-leg jeans and chunky sneakers for pure 90s grunge energy. Sustainable and styled."`
- Planning loop stores this in `session["fit_card"]`.

**Final output to user:**
```
Found: Faded Band Tee — $22 on depop (size M, good condition)

How to wear it: Pair this faded band tee with your Wide-leg jeans and Chunky platform
sneakers for a full 90s grunge look. Roll the sleeves once and tuck the front corner
slightly for shape.

Fit card: Thrifted this Faded Band Tee off depop for $22 — paired it with wide-leg
jeans and chunky sneakers for pure 90s grunge energy. Sustainable and styled.
```

---

## AI Tool Usage

I used Claude for two main implementation tasks. Here's exactly what I gave it and what came back.

---

### Instance 1: Implementing `search_listings`

**What I gave Claude:**

I pasted in the Tool 1 section from [planning.md](planning.md) — specifically the inputs block (parameter names, types, and what each represents), the return value description (list of listing dicts with all required fields), and the failure mode (return `[]` on no match, never raise). I also included the `load_listings()` signature from `utils/data_loader.py` so it knew what the raw data looked like.

**What it produced:**

A complete `search_listings()` implementation that:
- Called `load_listings()` to get all 40 listings
- Filtered by `max_price` and `size` (case-insensitive substring match)
- Scored each remaining listing by counting keyword overlaps against `title + description + style_tags`
- Dropped zero-score listings and sorted by score descending
- Returned the list of dicts (not scores) in sorted order

**What I changed before using it:**

The generated scoring function only checked `title` and `description` and didn't include `style_tags`. That was a problem because a lot of the listings in the dataset use tags like `"vintage"` or `"grunge"` that don't appear in the title at all. I added `" ".join(listing.get("style_tags", []))` to the concatenated text string so keyword matches against tags count toward the score. The `get(..., [])` fallback was also my addition becuase the generated code assumed `style_tags` always existed, which would've crashed on any listing missing that field.

The size filter also came back as an exact equality check (`l["size"] == size`). I changed it to `size_lower in l["size"].lower()` so that searching for `"M"` matches listings sized `"S/M"` as well as `"M"`. That matters for the dataset we have.

**How I verified it:**

I ran three queries against it before trusting it. First: `search_listings("vintage graphic tee", size=None, max_price=50)` : came back with results, all priced at or under $50. Second: `search_listings("designer ballgown", size="XXS", max_price=5)` : came back `[]` with no exception (this is the test in `test_tools.py:71-73`). Third: `search_listings("flannel", size=None, max_price=None)` : came back with listings that had "flannel" in the title or description, confirming description-only queries still work. All three matched what I expected from the spec, so I moved on.

---

### Instance 2: Implementing the planning loop (`run_agent`)

**What I gave Claude:**

I pasted in three sections from [planning.md](planning.md):

1. The **Planning Loop** section (the five numbered steps with every conditional branch spelled out — the `results == []` early return, the `session["selected_item"] = results[0]` assignment, etc.)
2. The **ASCII architecture diagram** showing the full data flow from user query → `search_listings` → `suggest_outfit` → `create_fit_card` → return, including where each error path branches off
3. The **State Management** section (the `session` dict fields and the description of one-direction state flow)

**What it produced:**

A complete `run_agent(query, wardrobe)` function that:
- Called `_new_session()` to initialize the session dict
- Used regex to parse `max_price` and `size` from the query string, then stripped those tokens to build a clean `description`
- Called `search_listings()`, checked for empty results, set `session["error"]` and returned early if empty
- Set `session["selected_item"] = results[0]` on success
- Called `suggest_outfit()` and stored the result in `session["outfit_suggestion"]`
- Called `create_fit_card()` and stored the result in `session["fit_card"]`
- Returned `session`

**What I changed before using it:**

The generated regex for `max_price` only caught `"$30"` — it missed `"under $30"` and `"under 30"`. I rewrote it as `r"(?:under\s*)?\$(\d+(?:\.\d+)?)|under\s+(\d+(?:\.\d+)?)"` with two capture groups so both forms work, then used `price_match.group(1) or price_match.group(2)` to grab whichever group fired.

The description cleanup was also too shallow. The generated version just stripped the matched price/size substrings but left filler words like `"looking for"`, `"i want"`, `"find me"` in the description string, which hurt the keyword scoring. I added a second `re.sub` pass to strip those stop words before calling `search_listings`.

The original also hardcoded `"M"`, `"L"`, `"XL"` as the only recognized standalone size tokens, which would have missed `"XXS"`, `"XXL"`, `"XXXL"`. I updated the regex alternation to include those. I kept bare `"S"` and `"M"` and `"L"` out of the standalone group on purpose — they're too ambiguous (they appear in normal words) — and only added them to the `"size M"` / `"in M"` patterns where context makes them unambiguous.

**How I verified it:**

I traced through the complete interaction example from planning.md manually against the generated code. I checked three things specifically: (1) does the loop stop after `search_listings` when results are empty and not call `suggest_outfit`? Yes — the `if not results: ... return session` block is in place. (2) Does the full happy path set all three session keys? Yes — I ran `python agent.py` and saw `selected_item`, `outfit_suggestion`, and `fit_card` all populated in the output. (3) Does the error message for no results include the search terms? Yes — the message formats `description`, `size`, and `max_price` into the string dynamically.

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing out the planning loop step by step in planning.md before touching any code made the early-return logic way clearer. When I was actually implementing `run_agent()`, I already knew exactly where to put the `if not results` check and what error message to return. Without that, I probably would have written the happy path first and then tried to bolt on error handling after, which usually ends up messier. The ASCII architecture diagram in planning.md was also super useful when I was wiring the tools together — I could just look at it and see which session keys got set at each step instead of mentally tracing the whole flow.

**One divergence from your spec, and why:**

My original spec said `suggest_outfit` should set `session["error"]` and return early if the wardrobe is empty (same as the no-results path). When I actually implemented it, I realized that was stricter than it needed to be — an empty wardrobe isn't really a failure, it just means the LLM needs a different prompt. So instead of stopping the loop, `suggest_outfit` now detects the empty wardrobe internally and switches to a "general styling advice" prompt, which means the user still gets an outfit suggestion and a fit card even without a populated wardrobe. I updated the spec in planning.md to match. The test `test_suggest_outfit_empty_wardrobe_no_crash` covers this behavior explicitly.
