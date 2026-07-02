#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Sequence
from textwrap import dedent
import os.path

import requests
from configupdater import ConfigUpdater

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

LATEST_RELEASE_URL = "https://api.github.com/repos/aquaproj/aqua/releases/latest"
CHECKSUMS_PATTERN = "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_{version}_checksums.txt"
URL_PATTERNS = {
    "linux-arm64": "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_linux_arm64.tar.gz",
    "linux-amd64": "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_linux_amd64.tar.gz",
    "darwin-arm64": "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_darwin_arm64.tar.gz",
    "darwin-amd64": "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_darwin_amd64.tar.gz",
    "windows-arm64": "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_windows_arm64.zip",
    "windows-amd64": "https://github.com/aquaproj/aqua/releases/download/v{version}/aqua_windows_amd64.zip",
}


def latest_aqua_version() -> str:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(LATEST_RELEASE_URL, headers=headers, verify=True)
    response.raise_for_status()
    return response.json()["tag_name"].removeprefix("v")


def update_pyproject_version(version: str) -> None:
    with open("pyproject.toml") as f:
        text = f.read()

    text = re.sub(r'(?m)^version = ".*"$', f'version = "{version}"', text, count=1)

    with open("pyproject.toml", "w") as f:
        f.write(text)


def update_setup_cfg(version: str) -> None:
    config = ConfigUpdater()
    config.read("setup.cfg")

    sha256sum = requests.get(CHECKSUMS_PATTERN.format(version=version), verify=True)
    sha256sum.raise_for_status()
    checksums = parse_sha256sum(sha256sum.text)

    data: dict[str, dict[str, str]] = {}
    for platform, url_pattern in URL_PATTERNS.items():
        url = url_pattern.format(version=version)
        basename = os.path.basename(url)
        data[platform] = {
            "url": url,
            "sha256": checksums[basename],
        }

    download_scripts = dedent(
        f"""
        [aqua]
        group = aqua-binary
        marker = sys_platform == "linux" and platform_machine == "aarch64"
        url = {data["linux-arm64"]["url"]}
        sha256 = {data["linux-arm64"]["sha256"]}
        extract = tar
        extract_path = aqua
        [aqua]
        group = aqua-binary
        marker = sys_platform == "linux" and platform_machine == "x86_64"
        url = {data["linux-amd64"]["url"]}
        sha256 = {data["linux-amd64"]["sha256"]}
        extract = tar
        extract_path = aqua
        [aqua]
        group = aqua-binary
        marker = sys_platform == "darwin" and platform_machine == "arm64"
        url = {data["darwin-arm64"]["url"]}
        sha256 = {data["darwin-arm64"]["sha256"]}
        extract = tar
        extract_path = aqua
        [aqua]
        group = aqua-binary
        marker = sys_platform == "darwin" and platform_machine == "x86_64"
        url = {data["darwin-amd64"]["url"]}
        sha256 = {data["darwin-amd64"]["sha256"]}
        extract = tar
        extract_path = aqua
        [aqua.exe]
        group = aqua-binary
        marker = sys_platform == "win32" and platform_machine == "AMD64"
        marker = sys_platform == "cygwin" and platform_machine == "x86_64"
        url = {data["windows-amd64"]["url"]}
        sha256 = {data["windows-amd64"]["sha256"]}
        extract = zip
        extract_path = aqua.exe
        [aqua.exe]
        group = aqua-binary
        marker = sys_platform == "win32" and platform_machine == "ARM64"
        marker = sys_platform == "cygwin" and platform_machine == "aarch64"
        url = {data["windows-arm64"]["url"]}
        sha256 = {data["windows-arm64"]["sha256"]}
        extract = zip
        extract_path = aqua.exe
        """,
    ).strip()

    config["setuptools_download"]["download_scripts"].set_values(
        download_scripts.splitlines(),
    )
    config.update_file()


def parse_sha256sum(data: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sha256_hash = line[:64]
        filename = line[66:]
        checksums[filename] = sha256_hash

    return checksums


def main(argv: Sequence[str] | None = None) -> int:
    logger = logging.getLogger()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aqua-version",
        type=str,
        default=None,
        help="aquaproj/aqua release version.",
    )

    args = parser.parse_args(argv)
    aqua_version: str | None = args.aqua_version
    write_pyproject = bool(aqua_version)
    logger.debug("Args: %s", args.__dict__)

    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)

    if aqua_version == "latest":
        aqua_version = latest_aqua_version()
    elif not aqua_version:
        aqua_version = str(pyproject["project"]["version"])

    aqua_version = aqua_version.removeprefix("v").split("-")[0]

    update_setup_cfg(aqua_version)

    if write_pyproject:
        update_pyproject_version(f"{aqua_version}-0")

    print(aqua_version)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
