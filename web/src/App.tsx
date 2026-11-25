import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  getGroup,
  searchGroups,
  type Group,
  type Match,
  type Reading,
} from "./api";
import GroupProfile from "./GroupProfile";
import NameMeaning from "./NameMeaning";

type View =
  | { kind: "start" }
  | { kind: "loading"; slow: boolean }
  | { kind: "error"; tooMany: boolean }
  | { kind: "none"; name: string; suggestions: string[]; readings: Reading[] }
  | { kind: "choose"; name: string; matches: Match[] }
  | { kind: "group"; group: Group; searchedName: string };

const EXAMPLES = ["Cozy Bear", "Lazarus Group", "UAC-0056"];
const MAX_LENGTH = 100;
const SLOW_AFTER_MS = 4_000;

async function loadView(
  name: string,
  groupId: number | null,
  signal: AbortSignal,
): Promise<View> {
  const { matches, suggestions, readings = [] } = await searchGroups(
    name,
    signal,
  );
  if (matches.length === 0) {
    return { kind: "none", name, suggestions, readings };
  }

  const chosen =
    matches.length === 1
      ? matches[0]
      : matches.find((match) => match.group_id === groupId);
  if (!chosen) return { kind: "choose", name, matches };

  return {
    kind: "group",
    group: await getGroup(chosen.group_id, signal),
    searchedName: chosen.matched_name,
  };
}

export default function App() {
  const [text, setText] = useState("");
  const [view, setView] = useState<View>({ kind: "start" });
  const currentRequest = useRef<AbortController | null>(null);

  async function showAddress() {
    currentRequest.current?.abort();
    const request = new AbortController();
    currentRequest.current = request;

    const params = new URLSearchParams(window.location.search);
    const name = (params.get("q") ?? "").trim().slice(0, MAX_LENGTH);
    const group = params.get("group");

    setText(name);
    if (!name) {
      setView({ kind: "start" });
      return;
    }

    setView({ kind: "loading", slow: false });
    const slowTimer = setTimeout(() => {
      if (!request.signal.aborted) setView({ kind: "loading", slow: true });
    }, SLOW_AFTER_MS);

    let next: View;
    try {
      next = await loadView(name, group ? Number(group) : null, request.signal);
    } catch (error) {
      const tooMany = error instanceof ApiError && error.status === 429;
      next = { kind: "error", tooMany };
    }

    clearTimeout(slowTimer);
    if (!request.signal.aborted) setView(next);
  }

  useEffect(() => {
    showAddress();
    window.addEventListener("popstate", showAddress);
    return () => {
      window.removeEventListener("popstate", showAddress);
      currentRequest.current?.abort();
    };
  }, []);

  useEffect(() => {
    document.title =
      view.kind === "group"
        ? `${view.group.main_name} | Codename`
        : "Codename: look up a hacker group";
  }, [view]);

  function go(name: string, groupId?: number) {
    const params = new URLSearchParams({ q: name });
    if (groupId !== undefined) params.set("group", String(groupId));

    const address = `/?${params}`;
    if (address !== window.location.pathname + window.location.search) {
      window.history.pushState(null, "", address);
    }
    showAddress();
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const name = text.trim();
    if (name) go(name);
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
              maxLength={MAX_LENGTH}
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
                  onClick={() => go(name)}
                >
                  {name}
                </button>
              ))}
            </p>
          )}

          {view.kind === "loading" && (
            <p>
              {view.slow
                ? "Waking up the server. This can take about a minute."
                : "Searching…"}
            </p>
          )}

          {view.kind === "error" && (
            <p>
              {view.tooMany
                ? "Too many searches at once. Please wait a minute and try again."
                : "Codename can’t reach its server right now. Please try again in a few minutes."}
            </p>
          )}

          {view.kind === "none" && (
            <>
              <p>
                No group found for “{view.name}”.{" "}
                {view.suggestions.length === 0 &&
                  view.readings.length === 0 &&
                  "Check the spelling, or try another name from the same article."}
              </p>
              <NameMeaning name={view.name} readings={view.readings} />
              {view.suggestions.length > 0 && (
                <>
                  <h2>Did you mean one of these?</h2>
                  <ul className="choices">
                    {view.suggestions.map((name) => (
                      <li key={name}>
                        <button type="button" onClick={() => go(name)}>
                          {name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}

          {view.kind === "choose" && (
            <>
              <h2>More than one group uses “{view.name}”</h2>
              <p>Security companies don’t always agree on names. Choose one:</p>
              <ul className="choices">
                {view.matches.map((match) => (
                  <li key={`${match.group_id}-${match.source.url}`}>
                    <button type="button" onClick={() => go(view.name, match.group_id)}>
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
        with the permission of The MITRE Corporation.{" "}
        <a href="/mitre-attack-license.txt">MITRE ATT&amp;CK license</a>. Vendor names
        come from{" "}
        <a href="https://github.com/MISP/misp-galaxy">MISP Galaxy</a> (CC0).
      </footer>
    </>
  );
}
