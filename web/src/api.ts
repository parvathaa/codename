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

export async function searchGroups(name: string): Promise<Match[]> {
  const result = await getJson<{ matches: Match[] }>(
    `/search?q=${encodeURIComponent(name)}`,
  );
  return result.matches;
}

export function getGroup(id: number): Promise<Group> {
  return getJson<Group>(`/groups/${id}`);
}
