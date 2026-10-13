"""Exercise channel publication against a local Git remote, including build races."""

import json
import subprocess
from pathlib import Path

import pytest

from scripts import ha_channels as channels

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    run("git", "init", "--bare", str(origin))
    run("git", "clone", str(origin), str(work))
    run("git", "checkout", "-b", "main", cwd=work)
    run("git", "config", "user.name", "Test author", cwd=work)
    run("git", "config", "user.email", "test@example.invalid", cwd=work)
    app = work / channels.STABLE
    (app / "translations").mkdir(parents=True)
    template = json.loads((ROOT / channels.STABLE / "manifest.json").read_text())
    (app / "manifest.json").write_text(json.dumps(template))
    (app / "config.json").write_text(json.dumps(channels.render(template, "stable", "0.1.4")))
    (app / "translations/cs.json").write_text('{"configuration":{}}')
    (work / "pyproject.toml").write_text('[project]\nversion="0.1.5"\n')
    (work / "README.md").write_text("Test source")
    run("git", "add", ".", cwd=work)
    run("git", "commit", "-m", "Source build", cwd=work)
    run("git", "push", "-u", "origin", "main", cwd=work)
    source = run("git", "rev-parse", "HEAD", cwd=work)
    run("git", "config", "user.name", "github-actions[bot]", cwd=work)
    monkeypatch.chdir(work)
    return work, source


def test_dev_and_stable_publish_without_changing_each_other(repository):
    work, source = repository
    assert channels.publish("dev", "0.1.5-dev42001", source)
    stable = json.loads((work / channels.STABLE / "config.json").read_text())
    dev = json.loads((work / channels.DEV / "config.json").read_text())
    assert stable["version"] == "0.1.4"
    assert dev["version"] == "0.1.5-dev42001"
    assert dev["slug"] != stable["slug"]
    assert dev["options"] == stable["options"]
    assert dev["boot"] == "manual"
    assert dev["image"] == stable["image"]
    assert channels.publish("stable", "0.1.5", source)
    assert json.loads((work / channels.DEV / "config.json").read_text()) == dev
    # A rerun may follow our own generated metadata commits.
    assert channels.publish("dev", "0.1.5-dev42002", source)
    assert not channels.publish("dev", "0.1.5-dev42001", source)
    assert not channels.publish("dev", "0.1.5-dev42002", source)
    assert run("git", "rev-parse", "HEAD") == run("git", "ls-remote", "origin", "main").split()[0]


def test_new_user_push_prevents_old_dev_publication(repository):
    work, source = repository
    run("git", "config", "user.name", "Test author")
    (work / "README.md").write_text("Newer source")
    run("git", "add", "README.md")
    run("git", "commit", "-m", "New source push")
    run("git", "push", "origin", "main")
    assert not channels.publish("dev", "0.1.5-dev42001", source)
    assert not (work / channels.DEV / "config.json").exists()


def test_old_stable_release_does_not_replace_newer_release(repository):
    work, source = repository
    assert channels.publish("stable", "0.1.5", source)
    (work / "pyproject.toml").write_text('[project]\nversion="0.1.4"\n')
    run("git", "add", "pyproject.toml")
    run("git", "commit", "-m", "Old release source")
    old_source = run("git", "rev-parse", "HEAD")
    run("git", "push", "origin", "main")
    assert not channels.publish("stable", "0.1.4", old_source)
    assert json.loads((work / channels.STABLE / "config.json").read_text())["version"] == "0.1.5"


def test_retry_when_a_publication_push_races(repository, monkeypatch):
    work, source = repository
    original = channels.git
    pushes = 0

    def racing_git(*args, **kwargs):
        nonlocal pushes
        if args[:1] == ("push",):
            pushes += 1
            if pushes == 1:
                return subprocess.CompletedProcess(args, 1, "", "Rejected by concurrent update")
        return original(*args, **kwargs)

    monkeypatch.setattr(channels, "git", racing_git)
    assert channels.publish("dev", "0.1.5-dev42001", source)
    assert pushes == 2
    assert json.loads((work / channels.DEV / "channel.json").read_text())["source"] == source


def test_unique_versions_and_invalid_inputs():
    assert channels.dev_version("0.1.5", 42, 1) == "0.1.5-dev42001"
    assert channels.dev_version("0.1.5", 42, 2) != channels.dev_version("0.1.5", 42, 1)
    assert channels.release_version("0.1.10") > channels.release_version("0.1.9")
    with pytest.raises(ValueError):
        channels.dev_version("0.1.5", 0, 1)
    with pytest.raises(ValueError):
        channels.release_version("0.1.5-dev42001")
    with pytest.raises(ValueError):
        channels.render({}, "dev", "dev")


def test_supervisor_dev_version_order():
    awesome = pytest.importorskip("awesomeversion").AwesomeVersion
    versions = [
        channels.dev_version("0.1.5", 41, 1),
        channels.dev_version("0.1.5", 42, 1),
        channels.dev_version("0.1.5", 42, 2),
        channels.dev_version("0.1.5", 100, 1),
        channels.dev_version("0.1.6", 101, 1),
    ]
    parsed = [awesome(version) for version in versions]
    assert all(version.valid and version.dev for version in parsed)
    assert all(right > left for left, right in zip(parsed, parsed[1:]))
