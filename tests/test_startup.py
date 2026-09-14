import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("key", [None, "", " \t"])
def test_missing_or_blank_key_starts_read_only_stdio_server(key: str | None) -> None:
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
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert "Traceback" not in result.stderr
