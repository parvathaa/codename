# Codename (working name)

A web app where someone enters a hacker group name, from any vendor, and learns
where the group is thought to be from, its other names, its attacks, history,
and what it is known for.

## Goals
- Learning project: Python, APIs, databases, Docker, Git/GitHub, React, Claude Code.
- Portfolio piece for jobs that people can really use.
- Audience: curious news readers (simple view) and security analysts (details,
  sources, technique IDs, export).

## How to work with me
- Give me the code in small, tested pieces and explain it in detail. Do not ask me to
  write code from scratch.
- I run the commands, Git steps and pull requests myself, so explain those too.
- I am fairly comfortable with Python. Assume I am new to SQL, JavaScript, Docker and Git.
- Use simple words and explain why, not only how.

## Proposed design (can change)
- FastAPI, PostgreSQL, React + TypeScript, Docker Compose.
- Data: MITRE ATT&CK and MISP Galaxy first; CISA and news feeds later. Check terms before use.
- An alias is a claim, with a vendor, source, relationship (same or overlaps) and
  confidence. Names from different vendors do not always match exactly.
- Every fact shown to users needs a source. Origins are suspected, not certain.

## Milestones
1. `lookup.py`: search a local MITRE ATT&CK JSON file by any alias (done)
2. PostgreSQL schema and import script (done)
3. FastAPI: `/search` and `/groups/{id}`, with tests (done)
4. React search and profile pages (done)
5. Docker Compose  <- current
6. GitHub Actions and deployment
7. News feeds, then AI summaries with citations

## Milestone 1 is done when
- `python3 lookup.py "cozy bear"` prints the group, its aliases and its description.
- Any letter case works.
- An unknown name gets a helpful message.
- It was merged through a pull request.
