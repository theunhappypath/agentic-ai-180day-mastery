# Drills

One folder per day's practical: `drills/day-NNN-<slug>/`. The lesson that defines each
drill is `docs/days/day-NNN-*.md`; its `produces:` frontmatter lists what belongs here.

Conventions:

- Run from the repo root so the shared environment is used: `uv run python drills/day-001-tokens/tokviz.py ...`
- Inputs you author go in the drill's `samples/`; generated outputs (plots, run logs) sit next to the script that made them.
- Tests, if a drill has them, are `test_*.py` inside the drill folder — `uv run pytest` picks them up.
- From Day 5, call models through `agentic_mastery.lab.call()`: it reads `lab.toml`, times the call, checks the tokens read, and appends one line to the repo-root `costs.jsonl` (schema: Day 1).
