# Codename

Look up a hacker group by any of its names.

Security companies often give the same group different names. For example,
APT29, Cozy Bear and Midnight Blizzard are names used for the same group.
Codename will let you enter a name you saw in the news and learn who the group
is, where it is thought to be from, and what it is known for.

## Who it's for

- **News readers** who want a plain-English explanation.
- **Security analysts** who want aliases, techniques and sources in one place.

## Status

Early development. The first milestone is a Python script that looks up a group
in MITRE ATT&CK data.

## Planned features

- Search by any known alias
- Explain naming patterns, such as "Panda" or "Typhoon"
- Show a group's history, attacks, tools and techniques
- Cite a source for every claim

## Planned tech

Python, FastAPI, PostgreSQL, React, TypeScript and Docker.

## Why I'm building it

I'm building Codename to learn how a full web application works, and to make
something useful for people who follow cybersecurity.

## A note on accuracy

Vendor names do not always match exactly, and a group's origin is usually an
assessment rather than a proven fact. Codename will show its sources and how
confident each claim is.
