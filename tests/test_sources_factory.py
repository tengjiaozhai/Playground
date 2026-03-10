from packages.common.sources import HybridAdapter, build_all_adapters


def test_build_all_adapters_modes() -> None:
    mock = build_all_adapters('mock')
    live = build_all_adapters('live')
    hybrid = build_all_adapters('hybrid')

    assert len(mock) == 6
    assert len(live) == 6
    assert len(hybrid) == 6
    assert all(not isinstance(a, HybridAdapter) for a in mock)
    assert all(isinstance(a, HybridAdapter) for a in hybrid)
