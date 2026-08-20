export function normalizedSearchTerms(query: string): string[] {
  return query
    .trim()
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter(Boolean);
}

export function matchesSearchTerms(query: string, values: Array<string | number | null | undefined>): boolean {
  const terms = normalizedSearchTerms(query);
  if (terms.length === 0) return true;
  const haystack = values.filter((value) => value != null).join(" ").toLocaleLowerCase();
  return terms.every((term) => haystack.includes(term));
}

