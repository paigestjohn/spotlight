# browser-use — Agent-Driven Browser Automation

**What:** Open-source Python library that lets an LLM control a real Chromium
browser. In Spotlight this is a legacy/adjacent automation option. The default
browser acquisition path is `dev-browser`, which benchmarked better on the
current Spotlight browser tasks.

**When to use:**

- You need to submit a search form with many fields and paginate through results (e.g. a corporate registry's advanced search)
- You need to click through to reveal content that JavaScript renders on interaction
- You need to export a CSV or PDF that's only accessible via a UI button
- You need to follow pagination beyond what firecrawl can handle statically

**When NOT to use:**

- Static pages → use `fetch` (firecrawl). Faster, cheaper, more reliable.
- Authenticated / court-record / gov-portal captures needing evidence handling → use `dev-browser` plus `web-archiving` and record the run in `evidence-bundle.json`.
- Bulk crawling → use firecrawl's crawl mode.

**Complement, not replacement:** browser-use can handle adjacent agent-driven
automation, but it is not Spotlight's default acquisition path.

## Setup

`browser-use` is not part of Spotlight's reviewed dependency pins. Do not install it automatically during setup or from an agent prompt. If the user explicitly wants this optional integration, review and pin the package first in `VALIDATED_DEPENDENCIES.md`, then update the setup policy and tests.

Optional cloud (SOTA model + CAPTCHA + stealth), requires `BROWSER_USE_API_KEY`:

```bash
export BROWSER_USE_API_KEY=bu-...
```

## Invocation

From the agent's perspective, browser-use is a shell-out via `execute-shell`. Invoke `shell-safety` first. Prefer task files or JSON over interpolating task text into a shell command. The wrapper script lives outside this repo — install it on the host so `browser-use` is on PATH, then:

```
write-file("{CASE_DIR}/research/browser-use-task.json", <serialized task JSON>)
execute-shell('browser-use-cli --task-file {CASE_DIR}/research/browser-use-task.json --output {CASE_DIR}/research/browser-use-<slug>.json')
```

For programmatic use (Python harness):

```python
from browser_use import Agent
from langchain_openai import ChatOpenAI  # or any LangChain-supported LLM

agent = Agent(
    task="Navigate to opencorporates.com, search for 'Acme Ltd' registered in UK, export the results as JSON",
    llm=ChatOpenAI(model="gpt-4o"),
)
result = await agent.run()
```

Store the resulting JSON/markdown into `{CASE_DIR}/research/` with a `browser-use-<slug>-<timestamp>.json` naming convention. Add the output path to the `sources[]` entry with `type: "browser_automation"` and `access_method: "full_text"`.

## Evidence handling

- Record the exact task string (prompt) sent to browser-use in the source entry under a `task` field, for reproducibility.
- Record the model used in the source entry.
- browser-use output is NOT chain-of-custody-grade by default. If the evidence needs legal defensibility, follow up with dev-browser and `web-archiving` to produce a canonical preserved copy and update `evidence-bundle.json`.

## Sensitive mode

In sensitive mode, browser-use SHOULD NOT run against live external sites (the same reasoning as `fetch`/`search`). It CAN still be used for local HTML files or pre-archived content in `{CASE_DIR}/research/archived/`. Guard in skill instructions; the adapter doesn't block browser-use by default because it's not a verb.

## Alternatives

| Need | Prefer |
|---|---|
| Static scrape | `fetch` (firecrawl) |
| Authenticated evidence capture | `dev-browser` + `web-archiving` |
| Tool discovery for a niche platform | `osint-navigator` integration |
| Bulk crawl | `firecrawl crawl` mode |
