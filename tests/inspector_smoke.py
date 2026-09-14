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
                            "args": [str(root / "tests/fixture_http_stdio_server.py")],
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
                {
                    "queries": [
                        {"query": q}
                        for q in [
                            "fixture-401",
                            "fixture-400",
                            "fixture-429",
                            "fixture-432",
                            "fixture-433",
                        ]
                    ]
                },
            ),
            (
                "rate_limited_batch",
                "fixture",
                "tools/call",
                {"queries": [{"query": "fixture-429"}, {"query": "still succeeds"}]},
            ),
            (
                "timeout_batch",
                "fixture",
                "tools/call",
                {
                    "queries": [
                        {"query": "fixture-timeout"},
                        {"query": "preserved"},
                        {"query": "fixture-trickle"},
                    ]
                },
            ),
            (
                "transport_and_upstream_errors",
                "fixture",
                "tools/call",
                {
                    "queries": [
                        {"query": q}
                        for q in [
                            "fixture-reset",
                            "fixture-500",
                            "fixture-418",
                            "fixture-malformed",
                        ]
                    ]
                },
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
                parameters = {
                    "search_depth",
                    "max_results",
                    "topic",
                    "time_range",
                    "start_date",
                    "end_date",
                    "include_domains",
                    "exclude_domains",
                    "country",
                    "language",
                    "exact_match",
                }
                assert set(schema) == {"queries", *parameters}
                assert set(schema["queries"]["items"]["properties"]) == {"query", *parameters}
                assert payload["tools"][0]["inputSchema"]["additionalProperties"] is False
                assert schema["queries"]["items"]["additionalProperties"] is False
                description = payload["tools"][0]["description"]
                assert "retry_after_seconds" in description and "30-second deadline" in description
            else:
                assert not payload["isError"]
                result = payload["structuredContent"]
                assert json.loads(payload["content"][0]["text"]) == result
                items = result["results"]
                submitted = [item["query"] for item in arguments["queries"]]
                assert [item["query"] for item in items] == submitted
                assert set(result) == {"partial", "results"}
                assert result["partial"] is (
                    scenario in {"partial_batch", "rate_limited_batch", "timeout_batch"}
                )
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
                elif scenario == "all_failed_batch":
                    assert statuses == ["error"] * 5
                    assert [item["error"]["category"] for item in items] == [
                        "invalid_or_missing_key",
                        "invalid_request",
                        "rate_limited",
                        "quota_exhausted",
                        "quota_exhausted",
                    ]
                    assert "plan_limit_exceeded" in items[3]["error"]["message"]
                    assert "payg_limit_exceeded" in items[4]["error"]["message"]
                    assert all(item["error"]["retry_after_seconds"] == 120 for item in items[2:])
                elif scenario == "rate_limited_batch":
                    assert statuses == ["error", "ok"]
                    assert items[0]["error"]["category"] == "rate_limited"
                    assert items[0]["error"]["retry_after_seconds"] == 120
                elif scenario == "timeout_batch":
                    assert statuses == ["error", "ok", "error"]
                    for index in (0, 2):
                        assert items[index]["error"]["category"] == "timeout_error"
                        assert set(items[index]["error"]) == {"category", "message"}
                else:
                    assert statuses == ["error"] * 4
                    assert [item["error"]["category"] for item in items] == [
                        "network_error",
                        "upstream_error",
                        "upstream_error",
                        "upstream_error",
                    ]
            observations.append(
                {
                    "scenario": scenario,
                    "exit_code": 0,
                    "arguments": arguments,
                    "response": payload,
                    "credential_check": "stdout and stderr contain no configured dummy key",
                }
            )

    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "client": f"MCP Inspector CLI {metadata['version']}",
        "transport": "stdio",
        "tavily_mode": "Controlled loopback HTTP service via HTTPX; no live Tavily calls",
        "fixture_attempt_deadline_seconds": 0.3,
        "production_attempt_deadline_seconds": 30.0,
        "real_account_429_432_433_verified": False,
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
