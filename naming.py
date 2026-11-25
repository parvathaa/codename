"""Guess who created a name from the vendor's public naming pattern.

This is only a guess: other companies sometimes use the same words.
"""

PATTERNS = {
    "CrowdStrike": {
        "page": "https://www.crowdstrike.com/adversaries/",
        "words": "panda bear kitten chollima spider jackal tiger leopard buffalo "
        "crane lynx wolf hawk ocelot sphinx saiga",
    },
    "Microsoft": {
        "page": "https://learn.microsoft.com/en-us/unified-secops/microsoft-threat-actor-naming",
        "words": "typhoon blizzard sandstorm sleet tempest tsunami flood cyclone "
        "hail dust rain",
    },
    "Palo Alto": {
        "page": "https://unit42.paloaltonetworks.com/threat-actor-groups-tracked-by-palo-alto-networks-unit-42/",
        "words": "taurus ursa serpens pisces libra scorpius",
    },
}

VENDOR_BY_WORD = {
    word: vendor
    for vendor, pattern in PATTERNS.items()
    for word in pattern["words"].split()
}


def likely_vendor(name):
    """Return the vendor a name's last word suggests, or None."""
    words = name.lower().split()
    if len(words) < 2 or words[-1] not in VENDOR_BY_WORD:
        return None

    vendor = VENDOR_BY_WORD[words[-1]]
    return {
        "name": vendor,
        "source": {
            "title": f"{vendor} naming pattern",
            "url": PATTERNS[vendor]["page"],
        },
    }
