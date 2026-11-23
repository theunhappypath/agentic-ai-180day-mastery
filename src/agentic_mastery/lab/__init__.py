"""The lab: one door for every model call, one settings file, one log.

    from agentic_mastery.lab import call

    result = call("What is a context window? One sentence.", day=5, tags={"drill": "demo"})
    print(result.text, result.record["latency_ms"], result.warnings)

Built on Day 5 from the pieces of Days 1-4: token counts and prices (Day 1), first-token
and total timing (Day 2), pinned temperature and seed (Day 3), an explicit window and a
truncation check (Day 4). Every later drill, and SENTINEL, calls models through here.
"""

from .call import Result, call
from .config import Config, ConfigError, Settings, load_config

__all__ = ["Config", "ConfigError", "Result", "Settings", "call", "load_config"]
