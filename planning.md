# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool searches the mock thrift marketplace dataset for listings that match the user’s request. It filters listings by description, title, category, size, price, condition, colors, brand, and platform, then returns matches ranked by relevance.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The user's item search terms, such as "vintage graphic tee" or "90s track jacket." This is matched against title, description, and style tags.
- `size` (str): Desired size or fit, such as "M" or "US 7." This is matched against the listing's `size` field.
- `max_price` (float): Maximum price threshold for the search.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
It returns a list of matching listing dictionaries. Each result contains at least: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If it fails or returns nothing because no listings match the query, the agent responds with a refinement suggestion and stops. It does not call `suggest_outfit` or `create_fit_card` on empty results.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool creates a styling recommendation for the selected new item using the user's wardrobe. It identifies complementary wardrobe pieces and suggests how to wear the item together.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The selected listing object from `search_listings`.
- `wardrobe` (dict): A wardrobe payload conforming to the schema in `data/wardrobe_schema.json`, containing an `items` list of pieces with `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.


**What it returns:**
<!-- Describe the return value -->
It returns a natural-language outfit suggestion string describing which wardrobe pieces pair best with the new item and how to style them.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the wardrobe is empty or no suitable outfit can be suggested, the agent returns a friendly fallback that explains it needs more wardrobe data and suggests the user add wardrobe items.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool generates a shareable fit-card caption that highlights the new thrifted item, where it was sourced, the price, and how it fits into the user’s existing style.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit_suggestion` (str): The natural-language styling recommendation returned by `suggest_outfit`.
- `new_item` (dict): The selected listing object from `search_listings`, including at minimum `title`, `price`, `platform`, `condition`, and `style_tags`.

**What it returns:**
<!-- Describe the return value -->
A shareable caption string (2–4 sentences) that names the item, its source platform and price, and weaves in the outfit suggestion as a style note. Example: "Thrifted this faded band tee from Depop for $22 — paired it with wide-leg jeans and chunky Docs for full 90s energy. Sustainable and styled."

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If `outfit_suggestion` is empty or `new_item` is missing required fields, the agent responds: "I wasn’t able to generate a fit card because the outfit or item data is incomplete. Make sure your search and styling steps completed successfully." It does not return a partial caption.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

**Step 1 — Parse query**
Extract `description` (str), `size` (str), and `max_price` (float) from the user message. These become the inputs to the first tool call.

**Step 2 — Call `search_listings(description, size, max_price)`**
- If `results == []` (empty list):
  → Set `session.error = "No listings found for '{description}' in size {size} under ${max_price}. Try broadening your search — remove the size filter or raise your budget."`
  → **Return early.** Do not call `suggest_outfit` or `create_fit_card`.
- If `len(results) >= 1`:
  → Set `session.selected_item = results[0]`
  → Proceed to Step 3.

**Step 3 — Call `suggest_outfit(session.selected_item, wardrobe)`**
- If `wardrobe["items"] == []` (empty wardrobe) OR the tool returns `None` or an empty string:
  → Set `session.error = "Your wardrobe is empty. Add a few items (like pants, shoes, or a jacket) so I can suggest styling combinations."`
  → **Return early.** Do not call `create_fit_card`.
- If `outfit_suggestion` is a non-empty string:
  → Set `session.outfit_suggestion = outfit_suggestion`
  → Proceed to Step 4.

**Step 4 — Call `create_fit_card(session.outfit_suggestion, session.selected_item)`**
- If `outfit_suggestion` is empty or `selected_item` is missing required fields (`title`, `price`, `platform`):
  → Set `session.error = "Couldn't generate a fit card — the outfit or item data is incomplete."`
  → **Return early.**
- If `fit_card` is a non-empty string:
  → Set `session.fit_card = fit_card`
  → Proceed to Step 5.

**Step 5 — Return session**
Return `session` containing `selected_item`, `outfit_suggestion`, and `fit_card`. The loop is complete.


---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
I think the session tracks three main pieces of state: `query_request`, `selected_listing`, and `outfit_suggestion`.

- `query_request` stores the parsed user intent and search constraints.
- `selected_listing` stores the top `search_listings` result.
- `outfit_suggestion` stores the string returned by `suggest_outfit`.

These values are passed sequentially: `search_listings` → `selected_listing` → `suggest_outfit` → `outfit_suggestion` → `create_fit_card`.

If a step fails, the agent uses the current state to return a clear error message and does not advance further.


---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | "No listings found for '{description}' in size {size} under ${max_price}. Try broadening your search — remove the size filter or raise your budget." Agent stops and returns this message without calling suggest_outfit or create_fit_card. |
| suggest_outfit | Wardrobe is empty | "Your wardrobe is empty. Add a few items (like pants, shoes, or a jacket) so I can suggest styling combinations." Agent stops and returns this message without calling create_fit_card. |
| create_fit_card | Outfit input is missing or incomplete | "I wasn't able to generate a fit card because the outfit or item data is incomplete. Make sure your search and styling steps completed successfully." Agent returns this message; no partial caption is shown. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
User query ("vintage graphic tee, size M, under $30")
    │
    ▼
Planning Loop
    │  parse → description="vintage graphic tee", size="M", max_price=30.0
    │
    ├─► search_listings(description, size, max_price)
    │       │
    │       ├── results=[]
    │       │       │
    │       │       ▼
    │       │   [ERROR] "No listings found for 'vintage graphic tee'   ◄─── early return
    │       │            in size M under $30. Try broadening your
    │       │            search — remove size or raise budget."
    │       │
    │       └── results=[item, ...]
    │               │  (list of listing dicts with id, title, price,
    │               │   platform, size, style_tags, condition, colors)
    │               ▼
    │           Session: selected_item = results[0]
    │               │
    ├─► suggest_outfit(selected_item, wardrobe)
    │       │  selected_item → dict from session
    │       │  wardrobe     → {"items": [...]} from user profile
    │       │
    │       ├── wardrobe["items"]=[] OR returns None/""
    │       │       │
    │       │       ▼
    │       │   [ERROR] "Your wardrobe is empty. Add pants, shoes,     ◄─── early return
    │       │            or a jacket so I can suggest combinations."
    │       │
    │       └── outfit_suggestion="Pair with wide-leg jeans and..."
    │               │
    │               ▼
    │           Session: outfit_suggestion = "Pair with wide-leg jeans..."
    │               │
    ├─► create_fit_card(outfit_suggestion, selected_item)
    │       │  outfit_suggestion → str from session
    │       │  selected_item    → dict from session
    │       │
    │       ├── outfit_suggestion="" OR selected_item missing title/price/platform
    │       │       │
    │       │       ▼
    │       │   [ERROR] "Couldn't generate a fit card — outfit or      ◄─── early return
    │       │            item data is incomplete."
    │       │
    │       └── fit_card="Thrifted this faded band tee from Depop..."
    │               │
    │               ▼
    │           Session: fit_card = "Thrifted this faded band tee..."
    │
    ▼
Return session { selected_item, outfit_suggestion, fit_card }
    │
    ▼
User sees: listing details + styling suggestion + shareable caption
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**search_listings:**
I'll use Claude. I'll paste in the Tool 1 block from this file (inputs, return value, failure mode) and ask it to implement `search_listings(description, size, max_price)` using `load_listings()` from the data loader. I'll verify the output by checking that the generated code: (1) filters on all three parameters, (2) returns an empty list (not `None` or an exception) when nothing matches, and (3) returns full listing dicts with all required fields. I'll test it with three queries: one that matches at least one listing, one that matches nothing, and one with only `description` set (no size or price).

**suggest_outfit:**
I'll use Claude. I'll paste in the Tool 2 block (inputs, return value, failure mode) and the wardrobe schema from `data/wardrobe_schema.json`. I'll ask it to implement `suggest_outfit(new_item, wardrobe)` that matches style_tags and colors between the new item and wardrobe items to produce a natural-language recommendation. I'll verify the output: (1) returns a non-empty string when a compatible wardrobe item exists, and (2) returns the fallback message (not an exception) when wardrobe is empty. I'll test with a populated wardrobe, an empty wardrobe, and a wardrobe with no style overlap.

**create_fit_card:**
I'll use Claude. I'll paste in the Tool 3 block (corrected inputs: `outfit_suggestion` str and `new_item` dict, return value, failure mode) plus the example fit-card format from this file. I'll ask it to implement `create_fit_card(outfit_suggestion, new_item)` that produces a 2–4 sentence shareable caption. I'll verify: (1) output includes `title`, `price`, and `platform` from `new_item`, (2) references the outfit suggestion content, and (3) returns the error message (not `None`) when inputs are missing. I'll test with a complete input, a missing `platform` field, and an empty `outfit_suggestion`.

**Milestone 4 — Planning loop and state management:**

I'll use Claude. I'll paste in the Planning Loop section (the five numbered steps with all conditional branches), the Architecture diagram (the ASCII version above), and the State Management section. I'll ask it to implement the planning loop as a function that calls each tool in order, checks return values at each step, sets session state, and returns early with a specific error message on failure. Before using the generated code I'll verify: (1) the loop stops after `search_listings` when results are empty and does not call `suggest_outfit`, (2) the loop stops after `suggest_outfit` when wardrobe is empty and does not call `create_fit_card`, and (3) all three session keys (`selected_item`, `outfit_suggestion`, `fit_card`) are set on the full success path. I'll trace through the complete interaction example (below) manually against the generated code to confirm outputs match.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — search_listings is called**

Tool called: `search_listings(description=”vintage graphic tee”, size=”M”, max_price=30.0)`

`search_listings` scans the listings dataset and returns two matches ranked by relevance:
```
results = [
  { “id”: “dp-041”, “title”: “Faded Band Tee”, “category”: “tops”, “size”: “M”,
    “price”: 22.0, “platform”: “Depop”, “condition”: “Good”,
    “colors”: [“black”, “grey”], “style_tags”: [“vintage”, “grunge”, “graphic”],
    “brand”: “Unknown”, “description”: “Worn-in black tee with faded band print” },
  { “id”: “pg-088”, “title”: “90s Graphic Tee”, “category”: “tops”, “size”: “M”,
    “price”: 28.0, “platform”: “Poshmark”, “condition”: “Like New”,
    “colors”: [“white”], “style_tags”: [“vintage”, “streetwear”, “graphic”],
    “brand”: “Hanes”, “description”: “Clean white tee with retro logo print” }
]
```
Since `results` is not empty, the planning loop sets `session.selected_item = results[0]` (the Faded Band Tee) and proceeds.

**Step 2 — suggest_outfit is called**

Tool called: `suggest_outfit(new_item=session.selected_item, wardrobe=user_wardrobe)`

where `user_wardrobe` is:
```
{ “items”: [
    { “id”: “w-01”, “name”: “Wide-leg jeans”, “category”: “bottoms”,
      “colors”: [“blue”], “style_tags”: [“baggy”, “casual”, “90s”] },
    { “id”: “w-02”, “name”: “Chunky platform sneakers”, “category”: “shoes”,
      “colors”: [“white”], “style_tags”: [“streetwear”, “chunky”, “90s”] }
  ]
}
```

`suggest_outfit` matches `style_tags` [“vintage”, “grunge”] on the tee against [“baggy”, “90s”] on the jeans and [“streetwear”, “90s”] on the sneakers, and returns:

`”Pair this faded band tee with your wide-leg jeans and chunky platform sneakers for a full 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape.”`

Since the result is a non-empty string, the planning loop sets `session.outfit_suggestion` to that string and proceeds.

**Step 3 — create_fit_card is called**

Tool called: `create_fit_card(outfit_suggestion=session.outfit_suggestion, new_item=session.selected_item)`

`create_fit_card` uses `title=”Faded Band Tee”`, `price=22.0`, `platform=”Depop”`, and the outfit suggestion to produce:

`”Thrifted this faded band tee from Depop for $22 — paired it with wide-leg jeans and chunky platform sneakers for full 90s grunge energy. Sustainable and styled. 🖤”`

The planning loop sets `session.fit_card` to that string. All three session keys are now set; the loop returns `session`.

**Final output to user:**

```
Found: Faded Band Tee — $22 on Depop (Good condition, size M)

How to wear it: Pair this faded band tee with your wide-leg jeans and chunky platform
sneakers for a full 90s grunge look. Roll the sleeves once and tuck the front corner
slightly for shape.

Fit card: Thrifted this faded band tee from Depop for $22 — paired it with wide-leg
jeans and chunky platform sneakers for full 90s grunge energy. Sustainable and styled. 🖤
```