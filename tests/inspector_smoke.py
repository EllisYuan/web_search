"""Run the independent MCP Inspector CLI against production and fixture stdio servers."""

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspector-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.inspector_package.resolve()
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    launcher = package / metadata["bin"]["mcp-inspector"]
    root = Path(__file__).resolve().parents[1]
    dummy_key = "dummy-secret-for-inspector"
    observations: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="web-search-smoke-") as temporary:
        config = Path(temporary) / "mcp.json"
        config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "production": {
                            "command": sys.executable,
                            "args": ["-m", "web_search"],
                            "env": {"TAVILY_API_KEY": dummy_key},
                        },
                        "fixture": {
                            "command": sys.executable,
                            "args": [str(root / "tests/fixture_stdio_server.py")],
                            "env": {"TAVILY_API_KEY": dummy_key},
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        scenarios = [
            ("discovery", "production", "tools/list", None),
            ("success", "fixture", "tools/call", "中文 MCP smoke"),
            ("unauthorized", "fixture", "tools/call", "fixture-401"),
        ]
        for scenario, server, method, query in scenarios:
            command = [
                "node",
                str(launcher),
                "--cli",
                "--config",
                str(config),
                "--server",
                server,
                "--method",
                method,
                "--format",
                "json",
            ]
            if query is not None:
                command += [
                    "--tool-name",
                    "web_search",
                    "--tool-args-json",
                    json.dumps({"queries": [{"query": query}]}, ensure_ascii=False),
                ]
            completed = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
            if dummy_key in completed.stdout + completed.stderr:
                raise RuntimeError("Smoke failed: credential was disclosed; output withheld.")
            if completed.returncode != 0:
                raise RuntimeError(f"Inspector {scenario} failed: {completed.stderr}")
            payload = json.loads(completed.stdout)["result"]
            if query is None:
                assert [tool["name"] for tool in payload["tools"]] == ["web_search"]
                assert payload["tools"][0]["inputSchema"]["properties"]["queries"]["maxItems"] == 1
            else:
                assert not payload["isError"]
                result = payload["structuredContent"]
                assert json.loads(payload["content"][0]["text"]) == result
                assert result["partial"] is False
                assert len(result["results"]) == 1
                item = result["results"][0]
                assert item["query"] == query
                if scenario == "success":
                    assert item["status"] == "ok"
                    assert item["candidates"][0]["rank"] == 1
                    assert item["candidates"][0]["url"] == "https://example.org/source"
                else:
                    assert item["status"] == "error"
                    assert item["error"]["category"] == "invalid_or_missing_key"
            observations.append({"scenario": scenario, "exit_code": 0, "response": payload})

    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "client": f"MCP Inspector CLI {metadata['version']}",
        "transport": "stdio",
        "tavily_mode": "HTTPX MockTransport fixtures; no live Tavily calls",
        "observations": observations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"PASS: discovery, success, 401; evidence: {args.output}")


if __name__ == "__main__":
    main()
