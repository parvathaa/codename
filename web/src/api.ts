export type Source = { title: string; url: string };

export type Match = {
  group_id: number;
  main_name: string;
  matched_name: string;
  relationship: string;
  confidence: string;
  source: Source;
};

export type Alias = {
  name: string;
  vendor: string | null;
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

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(`The API answered with status ${response.status}`);
  }
  return response.json();
}

export type SearchResult = { matches: Match[]; suggestions: string[] };

export function searchGroups(name: string): Promise<SearchResult> {
  return getJson<SearchResult>(`/search?q=${encodeURIComponent(name)}`);
}

export function getGroup(id: number): Promise<Group> {
  return getJson<Group>(`/groups/${id}`);
}
