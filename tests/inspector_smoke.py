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
        scenarios: list[tuple[str, str, str, dict[str, Any] | None]] = [
            ("discovery", "production", "tools/list", None),
            (
                "batch_with_per_query_overrides",
                "fixture",
                "tools/call",
                {
                    "search_depth": "basic",
                    "max_results": 5,
                    "queries": [
                        {"query": "中文 MCP smoke"},
                        {"query": "batch override", "search_depth": "advanced"},
                        {"query": "中文 MCP smoke"},
                    ],
                },
            ),
            (
                "partial_batch",
                "fixture",
                "tools/call",
                {
                    "queries": [
                        {"query": "中文 MCP smoke"},
                        {"query": "fixture-401"},
                        {"query": "fixture-400"},
                    ]
                },
            ),
            (
                "all_failed_batch",
                "fixture",
                "tools/call",
                {"queries": [{"query": "fixture-401"}, {"query": "fixture-400"}]},
            ),
        ]
        for scenario, server, method, arguments in scenarios:
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
            if arguments is not None:
                command += [
                    "--tool-name",
                    "web_search",
                    "--tool-args-json",
                    json.dumps(arguments, ensure_ascii=False),
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
            if arguments is None:
                assert [tool["name"] for tool in payload["tools"]] == ["web_search"]
                schema = payload["tools"][0]["inputSchema"]["properties"]
                assert schema["queries"]["minItems"] == 1
                assert schema["queries"]["maxItems"] == 20
                assert schema["max_results"]["maximum"] == 20
                assert "route" not in schema and "api_key" not in schema
            else:
                assert not payload["isError"]
                result = payload["structuredContent"]
                assert json.loads(payload["content"][0]["text"]) == result
                items = result["results"]
                submitted = [item["query"] for item in arguments["queries"]]
                assert [item["query"] for item in items] == submitted
                assert result["partial"] is (scenario == "partial_batch")
                statuses = [item["status"] for item in items]
                if scenario == "batch_with_per_query_overrides":
                    assert statuses == ["ok", "ok", "ok"]
                    assert items[0]["candidates"][0]["rank"] == 1
                    assert items[0]["candidates"][0]["url"].endswith("depth=basic")
                    assert items[1]["candidates"][0]["url"].endswith("depth=advanced")
                    # Duplicate query keeps its own item rather than being merged away.
                    assert items[2]["candidates"] == items[0]["candidates"]
                elif scenario == "partial_batch":
                    assert statuses == ["ok", "error", "error"]
                    assert items[1]["error"]["category"] == "invalid_or_missing_key"
                    assert items[2]["error"]["category"] == "invalid_request"
                else:
                    assert statuses == ["error", "error"]
                    assert [item["error"]["category"] for item in items] == [
                        "invalid_or_missing_key",
                        "invalid_request",
                    ]
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
    print(
        f"PASS: {', '.join(str(item['scenario']) for item in observations)}; "
        f"evidence: {args.output}"
    )


if __name__ == "__main__":
    main()
