# Codename

[![Tests](https://github.com/parvathaa/codename/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/parvathaa/codename/actions/workflows/tests.yml)

Look up a hacker group by any of its names.

**[Try it live](https://codename-lookup.netlify.app)**. The first search can take
about a minute while the free server wakes up.

Security companies often give the same group different names. For example,
APT29, Cozy Bear and Midnight Blizzard are names used for the same group.
Codename lets you enter a name you saw in the news and learn who the group is
and what it is known for.

## Who it's for

- **News readers** who want a plain-English explanation.
- **Security analysts** who want aliases, techniques and sources in one place.

## Status

Online, covering the groups in MITRE ATT&CK.

## What it does

- Finds a group by any name MITRE lists
- Suggests names when the spelling is close
- Lets you choose when a name belongs to more than one group
- Shows a summary, other names and a source
- Gives every search a link you can share

## Planned

- Explain naming patterns, such as "Panda" or "Typhoon"
- Show suspected origin, attacks, tools and techniques
- Add which vendor created each name, and more sources

## Run it

You need Docker.

1. Download the MITRE data:

   ```bash
   mkdir -p data
   curl -fL -o data/enterprise-attack.json https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json
   ```

2. Create your settings, start the app and load the data:

   ```bash
   cp .env.example .env
   docker compose up -d --build
   docker compose run --rm importer
   ```

3. Open http://localhost:8080

## Run the tests

You need Python 3.13, and the database must be running.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

## How it works

React page → FastAPI → PostgreSQL. A separate script imports the MITRE data.

| Part | On your computer | Online |
|---|---|---|
| Page | nginx in Docker | Netlify |
| API | Docker | Render |
| Database | Docker | Neon |

GitHub Actions runs the tests on every pull request. Render deploys changes to
`main` only after they pass.

## Why I'm building it

I'm building Codename to learn how a full web application works, and to make
something useful for people who follow cybersecurity.

## A note on accuracy

Vendor names do not always match exactly, and a group's origin is usually an
assessment rather than a proven fact. Codename links to its sources, and says
"unknown" when a source does not state how closely two names match.

## Data

© 2026 The MITRE Corporation. This work is reproduced and distributed with the
permission of The MITRE Corporation.
