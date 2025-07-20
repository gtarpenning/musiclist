#!/usr/bin/env python3
"""
Version management utilities for sf-music-calendar package
"""
import re
import sys
from pathlib import Path


def get_current_version():
    """Read current version from pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        sys.exit(1)

    content = pyproject_path.read_text()
    version_match = re.search(r'version = "([^"]+)"', content)

    if not version_match:
        print("❌ Version not found in pyproject.toml")
        sys.exit(1)

    return version_match.group(1)


def bump_patch_version(version_str):
    """Bump patch version (e.g., 0.1.1 -> 0.1.2)"""
    parts = version_str.split(".")
    if len(parts) != 3:
        print(f"❌ Invalid version format: {version_str}")
        sys.exit(1)

    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{major}.{minor}.{patch + 1}"
    except ValueError:
        print(f"❌ Invalid version format: {version_str}")
        sys.exit(1)


def update_version(new_version):
    """Update version in pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    updated_content = re.sub(
        r'version = "[^"]+"', f'version = "{new_version}"', content
    )

    pyproject_path.write_text(updated_content)


def main():
    if len(sys.argv) < 2:
        current_version = get_current_version()
        print(f"📋 Current version: {current_version}")
        return

    command = sys.argv[1]

    if command == "bump":
        current_version = get_current_version()
        new_version = bump_patch_version(current_version)
        update_version(new_version)
        print(f"🚀 Version bumped: {current_version} -> {new_version}")

    elif command == "get":
        current_version = get_current_version()
        print(current_version)

    else:
        print("❌ Unknown command. Use 'bump' or 'get'")
        sys.exit(1)


if __name__ == "__main__":
    main()
