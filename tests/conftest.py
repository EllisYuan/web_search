"""Deterministic OS capacity probe for contract tests, not for the Windows smoke."""

import psutil
import pytest


@pytest.fixture(autouse=True)
def available_contract_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    # Admission is still process-wide. Only ambient RAM availability is controlled;
    # worker allocation limits, browser execution and RSS monitoring remain real.
    # Resource refusal tests supply their own gate/capacity/failure at those boundaries.
    memory = psutil.virtual_memory()
    monkeypatch.setattr(psutil, "virtual_memory", lambda: memory._replace(available=8_000_000_000))
