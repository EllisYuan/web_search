import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("key", [None, "", " \t"])
def test_missing_or_blank_key_fails_before_stdio_starts(key: str | None) -> None:
    env = {name: value for name, value in os.environ.items() if name != "TAVILY_API_KEY"}
    if key is not None:
        env["TAVILY_API_KEY"] = key
    result = subprocess.run(
        [sys.executable, "-m", "web_search"],
        env=env,
        input="",
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "TAVILY_API_KEY" in result.stderr
    assert "MCP client" in result.stderr
    assert "Traceback" not in result.stderr
