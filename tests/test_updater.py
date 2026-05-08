"""Updater unit tests — version comparison + GitHub release parsing.

The download / apply / process-spawn paths aren't exercised here (they
require a real HTTP server + Windows). The check() endpoint is contract-
tested via the version comparison helpers.
"""

from __future__ import annotations

from backend import updater


def test_parse_version_basic():
    assert updater._parse_version("0.3.0") == (0, 3, 0)
    assert updater._parse_version("v0.3.0") == (0, 3, 0)
    assert updater._parse_version("V1.2.3") == (1, 2, 3)


def test_parse_version_short_pads():
    assert updater._parse_version("1") == (1, 0, 0)
    assert updater._parse_version("1.2") == (1, 2, 0)


def test_parse_version_pre_release_stripped():
    assert updater._parse_version("0.3.0-beta.1") == (0, 3, 0)
    assert updater._parse_version("0.3.0+build.7") == (0, 3, 0)


def test_is_newer_basic():
    assert updater.is_newer("0.3.0", "0.2.2") is True
    assert updater.is_newer("v0.3.0", "0.3.0") is False
    assert updater.is_newer("0.2.0", "0.3.0") is False


def test_is_newer_minor_vs_patch():
    assert updater.is_newer("0.3.1", "0.3.0") is True
    assert updater.is_newer("1.0.0", "0.99.99") is True


def test_release_from_raw_picks_zip_asset():
    raw = {
        "tag_name": "v0.3.1",
        "name": "v0.3.1 — booklet imposition",
        "body": "Adds saddle-stitch booklet.",
        "published_at": "2026-05-08T00:00:00Z",
        "assets": [
            {"name": "source.tar.gz", "browser_download_url": "https://x/src.tgz", "size": 100},
            {"name": "TrueColorPress-v0.3.1.zip", "browser_download_url": "https://x/zip", "size": 200_000_000},
        ],
    }
    rel = updater._release_from_raw(raw)
    assert rel is not None
    assert rel.tag == "v0.3.1"
    assert rel.version == "0.3.1"
    assert rel.zip_url == "https://x/zip"
    assert rel.zip_size == 200_000_000


def test_release_from_raw_no_zip_returns_none():
    raw = {
        "tag_name": "v0.3.1",
        "assets": [{"name": "source.tar.gz", "browser_download_url": "https://x/src.tgz"}],
    }
    assert updater._release_from_raw(raw) is None


def test_release_from_raw_missing_tag_returns_none():
    raw = {"assets": [{"name": "x.zip", "browser_download_url": "https://x/zip"}]}
    assert updater._release_from_raw(raw) is None


def test_supports_apply_false_in_dev():
    """In CI / dev (not frozen), auto-apply must refuse — there's no .exe to swap."""
    # We're not running under PyInstaller in pytest, so frozen=False.
    assert updater._supports_apply() is False
