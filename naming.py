"""Explain what a hacker group's name means in each vendor's naming system.

A reading says what a word means *if* the name follows that vendor's system.
It is a clue about the name, not proof of who is behind an attack.
"""

import re

CROWDSTRIKE = ("CrowdStrike adversaries", "https://www.crowdstrike.com/adversaries/")
CROWDSTRIKE_REPORT = (
    "CrowdStrike 2025 Global Threat Report",
    "https://go.crowdstrike.com/rs/281-OBQ-266/images/CrowdStrikeGlobalThreatReport2025.pdf",
)
MICROSOFT = (
    "How Microsoft names threat actors",
    "https://learn.microsoft.com/en-us/defender-xdr/microsoft-threat-actor-naming",
)
UNIT_42 = (
    "Threat actor groups tracked by Unit 42",
    "https://unit42.paloaltonetworks.com/threat-actor-groups-tracked-by-palo-alto-networks-unit-42/",
)
GOOGLE = (
    "Google's updated threat actor naming system",
    "https://cloud.google.com/blog/topics/threat-intelligence/updated-cyber-threat-actor-naming-system",
)
MANDIANT = (
    "How Mandiant tracks uncategorized threat actors",
    "https://cloud.google.com/blog/topics/threat-intelligence/how-mandiant-tracks-uncategorized-threat-actors",
)
SECUREWORKS = (
    "Secureworks threat groups",
    "https://docs.taegis.secureworks.com/intelligence/threat_groups/",
)

# (vendor, source, {word: meaning}) for names where the last word has a meaning.
LAST_WORDS = [
    ("CrowdStrike", CROWDSTRIKE, {
        "bear": "Russia",
        "bison": "Belarus",
        "chollima": "North Korea",
        "jackal": "hacktivists",
        "kitten": "Iran",
        "leopard": "Pakistan",
        "ocelot": "Colombia",
        "panda": "China",
        "spider": "cybercriminals",
        "tiger": "India",
        "wolf": "Turkey",
    }),
    ("CrowdStrike", CROWDSTRIKE_REPORT, {
        "buffalo": "Vietnam",
        "crane": "South Korea",
        "hawk": "Syria",
        "lynx": "Georgia",
    }),
    ("Microsoft", MICROSOFT, {
        "blizzard": "Russia",
        "cyclone": "Vietnam",
        "derecho": "Spain",
        "dust": "Türkiye",
        "flood": "influence operations",
        "fog": "the United Kingdom",
        "freeze": "Canada",
        "frost": "Ukraine",
        "gale": "Germany",
        "gust": "the United Arab Emirates",
        "hail": "South Korea",
        "haze": "Syria",
        "heatwave": "Israel",
        "lightning": "the Palestinian Authority",
        "monsoon": "India",
        "rain": "Lebanon",
        "sandstorm": "Iran",
        "sleet": "North Korea",
        "squall": "Singapore",
        "swell": "New Zealand",
        "tempest": "financially motivated groups",
        "tornado": "the United States",
        "tsunami": "companies that sell cyberweapons",
        "typhoon": "China",
        "vortex": "Pakistan",
        "waterspout": "Australia",
    }),
    ("Palo Alto", UNIT_42, {
        "draco": "Pakistan",
        "libra": "financially motivated cybercrime groups",
        "lynx": "Belarus",
        "pisces": "North Korea",
        "scorpius": "ransomware groups",
        "serpens": "Iran",
        "taurus": "China",
        "ursa": "Russia",
    }),
    ("Google", GOOGLE, {
        "castle": "China",
        "comet": "cybercriminals",
        "ion": "Iran",
        "neptune": "North Korea",
        "relic": "Russia",
    }),
]

# The same, for names where the first word has a meaning.
FIRST_WORDS = [
    ("Secureworks", SECUREWORKS, {
        "aluminum": "Palestine",
        "bronze": "China",
        "cobalt": "Iran",
        "copper": "Pakistan",
        "gold": "cybercrime",
        "iron": "Russia",
        "lithium": "Lebanon",
        "nickel": "North Korea",
        "platinum": "the United States",
        "radium": "a red team",
        "silver": "Singapore",
        "steel": "the United Kingdom",
        "tin": "Vietnam",
        "tungsten": "South Korea",
        "zinc": "India",
    }),
]

# (vendor, source, pattern, meaning) for names that are a code and a number.
NUMBERED = [
    ("Microsoft", MICROSOFT, r"storm-?\d{4}", "a group still in development when it was named"),
    ("Mandiant", MANDIANT, r"unc\d+", "activity that was uncategorized when it was named"),
    ("Mandiant", MANDIANT, r"fin\d+", "a financially motivated group"),
]

# Ordinary words that follow a metal in names from other companies.
NOT_SECUREWORKS = {"actor", "gang", "group", "hackers", "team"}


def reading(vendor, source, clue, meaning):
    return {
        "vendor": vendor,
        "clue": clue,
        "meaning": meaning,
        "source": {"title": source[0], "url": source[1]},
    }


def look_up(table, word):
    return [
        reading(vendor, source, word.title(), words[word])
        for vendor, source, words in table
        if word in words
    ]


def decode(name):
    """Return every meaning the name could have."""
    words = name.lower().split()
    if not words:
        return []

    if len(words) == 1:
        for vendor, source, pattern, meaning in NUMBERED:
            if re.fullmatch(pattern, words[0]):
                clue = re.match(r"[a-z]+", words[0]).group()
                clue = clue.title() if clue == "storm" else clue.upper()
                return [reading(vendor, source, clue, meaning)]
        return look_up(LAST_WORDS, words[0]) + look_up(FIRST_WORDS, words[0])

    readings = look_up(LAST_WORDS, words[-1])
    if not readings and words[-1] not in NOT_SECUREWORKS:
        readings = look_up(FIRST_WORDS, words[0])
    return readings


def likely_vendor(name):
    """Return the one vendor a full name points to, or None if it is unclear."""
    words = name.lower().split()
    if len(words) < 2:
        return None

    readings = decode(name)
    if readings and readings[0]["vendor"] != "Secureworks":
        # "Iron Tiger" fits two systems at once, so it points to neither.
        readings = readings + look_up(FIRST_WORDS, words[0])
    if len({found["vendor"] for found in readings}) != 1:
        return None
    return {"name": readings[0]["vendor"], "source": readings[0]["source"]}


# Names MISP uses for vendors that we call something else.
SAME_VENDOR = {"Google Cloud Blog": "Google"}


def meaning_from(name, vendors):
    """Return the name's meaning in the system of one of these vendors, or None."""
    known = {SAME_VENDOR.get(vendor, vendor) for vendor in vendors}
    for found in decode(name):
        if found["vendor"] in known:
            return found
    return None
