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
- `new_item` (dict): The selected listing object from `search_listings`.
- `wardrobe` (dict): A wardrobe payload conforming to the schema in `data/wardrobe_schema.json`, containing an `items` list of pieces with `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.


**What it returns:**
<!-- Describe the return value -->
An outfit suggestion string in natural language of which wardrobe pieces pair best with the new item and how to style them.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If the wardrobe is empty or no suitable outfit can be suggested, the agent returns a friendly fallback that explains it needs more wardrobe data and suggests the user add wardrobe items.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The agent starts by parsing the user's request for a product description, size, and budget. It calls `search_listings` first because shopping must succeed before styling. If `search_listings` returns at least one result, the agent selects the top match and calls `suggest_outfit` with that item and the user's wardrobe. If the outfit suggestion succeeds, it then calls `create_fit_card` to generate the social caption and finishes.

The loop is done once the app has either returned a final answer with listing, styling, and fit card, or returned an error/refinement response for an earlier failure.


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
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

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

```mermaid
flowchart TD
    U[User query] --> P[Planning Loop]
    P --> S1[search_listings(description, size, max_price)]
    S1 -->|results=[]| E1[ERROR: "No listings found..." → return]
    S1 -->|results=[item,...]| T1[Session: selected_item = results[0]]
    T1 --> S2[suggest_outfit(selected_item, wardrobe)]
    S2 --> T2[Session: outfit_suggestion = "..."]
    T2 --> S3[create_fit_card(outfit_suggestion, selected_item)]
    S3 --> T3[Session: fit_card = "..."]
    T3 --> O[Return session]
```

This architecture reflects the linear flow from user query through the planning loop and tool chain, with the search failure path returning before outfit creation as an early exit.

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

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The agent will first call search_listings("vintage graphic tee", max_price=30.0).

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
Step 1 returned the matching listings sorted by relevance. FitFindr (the agent) picks the top result: "Faded Band Tee — $22, Depop, Good condition." 
Then the agent calls suggest_outfit(new_item=top_result, wardrobe=example_wardrobe).

**Step 3:**
<!-- Continue until the full interaction is complete -->
suggest_outfit returns a styling recommendation like: "Pair this with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape." 

The agent then calls create_fit_card(outfit=that_suggestion, new_item=top_result)
which returns the outfit suggestion to the user. 

**Final output to user:**
<!-- What does the user actually see at the end? -->
The user sees the combined response that includes the selected listing, how to style it, and a shareable caption, for example:
“Faded Band Tee — $22, Depop, Good condition.”