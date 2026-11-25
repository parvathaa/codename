import { useRef, useState, type FormEvent } from "react";
import { getGroup, searchGroups, type Group, type Match } from "./api";
import GroupProfile from "./GroupProfile";

type View =
  | { kind: "start" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "none"; name: string }
  | { kind: "choose"; name: string; matches: Match[] }
  | { kind: "group"; group: Group; searchedName: string };

const EXAMPLES = ["Cozy Bear", "Lazarus Group", "UAC-0056"];

export default function App() {
  const [text, setText] = useState("");
  const [view, setView] = useState<View>({ kind: "start" });
  const latestRequest = useRef(0);

  async function show(load: () => Promise<View>) {
    const request = ++latestRequest.current;
    setView({ kind: "loading" });

    let next: View;
    try {
      next = await load();
    } catch {
      next = { kind: "error" };
    }

    if (request === latestRequest.current) {
      setView(next);
    }
  }

  function openGroup(match: Match) {
    return show(async () => ({
      kind: "group",
      group: await getGroup(match.group_id),
      searchedName: match.matched_name,
    }));
  }

  function search(name: string) {
    return show(async () => {
      const matches = await searchGroups(name);
      if (matches.length === 0) return { kind: "none", name };
      if (matches.length > 1) return { kind: "choose", name, matches };
      return {
        kind: "group",
        group: await getGroup(matches[0].group_id),
        searchedName: matches[0].matched_name,
      };
    });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const name = text.trim();
    if (name) search(name);
  }

  return (
    <>
      <main>
        <header>
          <h1>Codename</h1>
          <p>One hacker group can have many names. Look up any of them.</p>
        </header>

        <form onSubmit={handleSubmit}>
          <label htmlFor="name">Hacker group name</label>
          <div className="search-row">
            <input
              id="name"
              type="search"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Cozy Bear"
              maxLength={100}
              autoComplete="off"
            />
            <button type="submit">Search</button>
          </div>
        </form>

        <section aria-live="polite" aria-busy={view.kind === "loading"}>
          {view.kind === "start" && (
            <p className="examples">
              Try{" "}
              {EXAMPLES.map((name) => (
                <button
                  key={name}
                  type="button"
                  className="link"
                  onClick={() => {
                    setText(name);
                    search(name);
                  }}
                >
                  {name}
                </button>
              ))}
            </p>
          )}

          {view.kind === "loading" && <p>Searching…</p>}

          {view.kind === "error" && (
            <p>
              Codename can’t reach its database right now. Please try again in a
              moment.
            </p>
          )}

          {view.kind === "none" && (
            <p>
              No group found for “{view.name}”. Check the spelling, or try
              another name from the same article.
            </p>
          )}

          {view.kind === "choose" && (
            <>
              <h2>More than one group uses “{view.name}”</h2>
              <p>Security companies don’t always agree on names. Choose one:</p>
              <ul className="choices">
                {view.matches.map((match) => (
                  <li key={`${match.group_id}-${match.source.url}`}>
                    <button type="button" onClick={() => openGroup(match)}>
                      {match.main_name}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {view.kind === "group" && (
            <GroupProfile group={view.group} searchedName={view.searchedName} />
          )}
        </section>
      </main>

      <footer>
        © 2026 The MITRE Corporation. This work is reproduced and distributed
        with the permission of The MITRE Corporation.
      </footer>
    </>
  );
}
