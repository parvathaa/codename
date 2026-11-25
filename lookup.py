"""Look up a hacker group by any of its names, using MITRE ATT&CK data."""

import json
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "enterprise-attack.json"


def load_groups():
    """Read the MITRE file and return only the active hacker groups."""
    with open(DATA_FILE, encoding="utf-8") as file:
        data = json.load(file)

    groups = []
    for item in data["objects"]:
        is_group = item["type"] == "intrusion-set"
        is_retired = item.get("revoked") or item.get("x_mitre_deprecated")
        if is_group and not is_retired:
            groups.append(item)
    return groups


def normalize(name):
    """Make names comparable: lowercase, with single spaces."""
    return " ".join(name.lower().split())


def build_index(groups):
    """Map every name to the list of groups that use it."""
    index = {}
    for group in groups:
        names = {normalize(group["name"])}
        for alias in group.get("aliases", []):
            names.add(normalize(alias))

        for name in names:
            index.setdefault(name, []).append(group)
    return index


def print_group(group):
    """Show one group in the terminal."""
    other_names = [a for a in group.get("aliases", []) if a != group["name"]]

    print(f"\n{group['name']}")
    print(f"Also known as: {', '.join(other_names) or 'no other names listed'}")
    print(f"\n{group.get('description', 'No description available.')}")


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 lookup.py "group name"')
        return 1

    if not DATA_FILE.exists():
        print(f"Data file not found: {DATA_FILE}")
        return 1

    search = " ".join(sys.argv[1:])
    index = build_index(load_groups())
    matches = index.get(normalize(search), [])

    if not matches:
        print(f'No group found for "{search}". Check the spelling or try another name.')
        return 1

    for group in matches:
        print_group(group)

    print("\nSource: MITRE ATT&CK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
