export type Source = { title: string; url: string };

export type Match = {
  group_id: number;
  main_name: string;
  matched_name: string;
  relationship: string;
  confidence: string;
  source: Source;
};

export type Vendor = { name: string; source: Source };

export type Alias = {
  name: string;
  // Missing only while an older version of the API is still running.
  vendors?: Vendor[];
  likely_vendor?: Vendor | null;
  relationship: string;
  confidence: string;
  source: Source;
};

export type Group = {
  id: number;
  mitre_id: string | null;
  main_name: string;
  suspected_origin: string | null;
  summary: string | null;
  source: Source;
  aliases: Alias[];
};

const RETRY_FOR_MS = 90_000;
const RETRY_EVERY_MS = 3_000;
const ONE_TRY_MS = 30_000;

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`The API answered with status ${status}`);
  }
}

function pause(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

// A sleeping server answers 502, 503 or 504, or not at all, until it wakes up.
async function fetchWhenAwake(path: string, signal: AbortSignal) {
  const giveUpAt = Date.now() + RETRY_FOR_MS;

  while (true) {
    let failure: Error;
    try {
      const response = await fetch(`/api${path}`, {
        signal: AbortSignal.any([signal, AbortSignal.timeout(ONE_TRY_MS)]),
      });
      if (![502, 503, 504].includes(response.status)) return response;
      failure = new ApiError(response.status);
    } catch (error) {
      failure = error as Error;
    }

    if (signal.aborted || Date.now() + RETRY_EVERY_MS > giveUpAt) throw failure;
    await pause(RETRY_EVERY_MS);
    if (signal.aborted) throw failure;
  }
}

async function getJson<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetchWhenAwake(path, signal);
  if (!response.ok) throw new ApiError(response.status);
  return response.json();
}

export type SearchResult = { matches: Match[]; suggestions: string[] };

export function searchGroups(name: string, signal: AbortSignal) {
  return getJson<SearchResult>(`/search?q=${encodeURIComponent(name)}`, signal);
}

export function getGroup(id: number, signal: AbortSignal) {
  return getJson<Group>(`/groups/${id}`, signal);
}
