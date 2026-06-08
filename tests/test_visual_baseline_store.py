from pathlib import Path

from PIL import Image

from core.visual_baseline_store import BaselineStore


def _make_image(path: Path, color: str = "white") -> None:
    Image.new("RGB", (120, 120), color=color).save(path, format="PNG")


def test_initialize_creates_database(tmp_path):
    store = BaselineStore(str(tmp_path / "baselines.db"))
    store.initialize()

    assert (tmp_path / "baselines.db").exists()


def test_save_and_get_baseline_round_trip(tmp_path):
    source = tmp_path / "source.png"
    _make_image(source)
    store = BaselineStore(str(tmp_path / "baselines.db"))
    store.initialize()

    saved_path = store.save_baseline("home", "https://example.com", str(source), "SCAN-1")
    record = store.get_baseline("home")

    assert saved_path is not None
    assert record["page_id"] == "home"
    assert record["page_url"] == "https://example.com"
    assert Path(record["screenshot_path"]).exists()
    assert len(store.get_baseline_versions("home")) == 1


def test_get_baseline_unknown_returns_none(tmp_path):
    store = BaselineStore(str(tmp_path / "baselines.db"))
    store.initialize()

    assert store.get_baseline("missing") is None


def test_refresh_baseline_replaces_record(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _make_image(first, "white")
    _make_image(second, "black")
    store = BaselineStore(str(tmp_path / "baselines.db"))
    store.initialize()
    store.save_baseline("home", "https://example.com", str(first), "SCAN-1")

    refreshed = store.refresh_baseline("home", str(second), "SCAN-2")
    record = store.get_baseline("home")

    assert refreshed == record["screenshot_path"]
    assert record["scan_id"] == "SCAN-2"
    assert len(store.get_baseline_versions("home")) == 2


def test_list_baselines_returns_all_records(tmp_path):
    source = tmp_path / "source.png"
    _make_image(source)
    store = BaselineStore(str(tmp_path / "baselines.db"))
    store.initialize()
    store.save_baseline("home", "https://example.com/home", str(source), "SCAN-1")
    store.save_baseline("settings", "https://example.com/settings", str(source), "SCAN-1")

    baselines = store.list_baselines()

    assert {baseline["page_id"] for baseline in baselines} == {"home", "settings"}
