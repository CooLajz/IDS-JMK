"""Publish HA channel manifests only after their immutable images have been built."""

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path

STABLE = Path("home-assistant/ids_jmk")
DEV = Path("home-assistant/ids_jmk_dev")
GENERATED = {
    str(STABLE / "config.json"),
    str(DEV / "config.json"),
    str(DEV / "CHANGELOG.md"),
    str(DEV / "translations/cs.json"),
    str(DEV / "channel.json"),
}


def git(*args, check=True):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=check)


def release_version(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Verze vydání musí mít tvar X.Y.Z.")
    return tuple(map(int, version.split(".")))


def dev_version(base, run_number, attempt):
    release_version(base)
    if run_number < 1 or not 1 <= attempt < 1000:
        raise ValueError("Číslo sestavení musí být kladné a pokus musí být v rozsahu 1–999.")
    # AwesomeVersion orders a single dev counter correctly; multiple suffix numbers do not.
    return f"{base}-dev{run_number * 1000 + attempt}"


def render(template, channel, version):
    config = {**template, "version": version}
    if channel == "stable":
        release_version(version)
    elif channel == "dev":
        if not re.fullmatch(r"\d+\.\d+\.\d+-dev[1-9]\d*", version):
            raise ValueError("Neplatná verze vývojového sestavení.")
        config.update(
            name="IDS JMK Parser (Dev)",
            slug="ids_jmk_parser_dev",
            description="Vývojové sestavení parseru IDS JMK z větve main.",
            stage="experimental",
            boot="manual",
        )
    else:
        raise ValueError("Neznámý kanál.")
    return config


def source_file(source, path):
    return git("show", f"{source}:{path}").stdout


def same_source(source, head):
    if git("merge-base", "--is-ancestor", source, head, check=False).returncode:
        return False
    changed = set(git("diff", "--name-only", source, head).stdout.splitlines())
    if not changed <= GENERATED:
        return False
    # Only our channel publication commits may have followed the source build.
    commits = git("log", "--format=%an%x09%s", f"{source}..{head}").stdout.splitlines()
    return all(line.startswith("github-actions[bot]\tUpdate Home Assistant ") for line in commits)


def publish(channel, version, source):
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Zdroj musí být plný SHA commitu.")
    template = json.loads(source_file(source, STABLE / "manifest.json"))
    config = render(template, channel, version)
    base = tomllib.loads(source_file(source, "pyproject.toml"))["project"]["version"]
    if channel == "stable" and base != version:
        raise ValueError("Verze vydání nesouhlasí se zdrojovým commitem.")
    if channel == "dev" and not version.startswith(base + "-dev"):
        raise ValueError("Verze dev nesouhlasí se zdrojovým commitem.")
    folder = DEV if channel == "dev" else STABLE
    files = {folder / "config.json": json.dumps(config, ensure_ascii=False, indent=2) + "\n"}
    if channel == "dev":
        files[DEV / "translations/cs.json"] = source_file(source, STABLE / "translations/cs.json")
        files[DEV / "channel.json"] = json.dumps({"version": version, "source": source}, indent=2) + "\n"
        files[DEV / "CHANGELOG.md"] = (
            f"# {version}\n\nVývojové sestavení z větve `main`.\n\n"
            f"Zdroj: [commit {source[:7]}](https://github.com/CooLajz/IDS-JMK/commit/{source}).\n\n"
            "Sestavení prošlo kontrolami API, webu, integrace a kontejnerů na AMD64 a ARM64.\n"
        )
    for _ in range(3):
        git("fetch", "origin", "+refs/heads/main:refs/remotes/origin/main")
        head = git("rev-parse", "origin/main").stdout.strip()
        if channel == "dev" and not same_source(source, head):
            print("Nabídka dev se nemění: větev main již obsahuje novější změny.")
            return False
        git("checkout", "-B", "main", "origin/main")
        path = folder / "config.json"
        if path.exists():
            previous = json.loads(path.read_text())["version"]
            if channel == "stable" and release_version(previous) > release_version(version):
                print("Nabídka stabilní verze se nemění: již je publikováno novější vydání.")
                return False
            if channel == "dev":

                def parts(v):
                    return tuple(map(int, re.findall(r"\d+", v)))

                if parts(previous) > parts(version):
                    print("Nabídka dev se nemění: již je publikováno novější sestavení.")
                    return False
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        git("add", "--", *(str(path) for path in files))
        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            print("Nabídka HA již odpovídá sestavení.")
            return False
        git("commit", "-m", f"Update Home Assistant {channel} manifest to {version} [skip ci]")
        if git("push", "origin", "HEAD:main", check=False).returncode == 0:
            print(f"Nabídka HA aktualizována: {channel} {version}.")
            return True
    raise RuntimeError("Nabídku HA nelze publikovat. Ověřte oprávnění workflow a pravidla větve main.")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    dev = commands.add_parser("dev-version")
    dev.add_argument("--run-number", type=int, required=True)
    dev.add_argument("--attempt", type=int, required=True)
    output = commands.add_parser("render")
    output.add_argument("--channel", choices=("stable", "dev"), required=True)
    output.add_argument("--version", required=True)
    output.add_argument("--output", type=Path, required=True)
    update = commands.add_parser("publish")
    update.add_argument("--channel", choices=("stable", "dev"), required=True)
    update.add_argument("--version", required=True)
    update.add_argument("--source", required=True)
    args = parser.parse_args()
    if args.command == "dev-version":
        base = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
        print(dev_version(base, args.run_number, args.attempt))
    elif args.command == "render":
        config = render(json.loads((STABLE / "manifest.json").read_text()), args.channel, args.version)
        args.output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    else:
        publish(args.channel, args.version, args.source)


if __name__ == "__main__":
    main()
