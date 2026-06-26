from __future__ import annotations


def test_quantum_settings_path_isolated() -> None:
    from goldsilver.data.settings import settings_path as gs_path
    from quantum.data.settings import settings_path as q_path

    assert q_path() != gs_path()
    assert q_path().parent.name == "quantum"


def test_quantum_settings_defaults() -> None:
    from quantum.data.presets import ETF_DEFAULTS, PUREPLAY_DEFAULTS
    from quantum.data.settings import QuantumSettings

    s = QuantumSettings()
    assert s.etf_tickers == list(ETF_DEFAULTS)
    assert s.stock_tickers == list(PUREPLAY_DEFAULTS)
    assert s.news_enabled is True
