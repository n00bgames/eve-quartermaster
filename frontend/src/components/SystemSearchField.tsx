import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { SystemSearchResult } from "../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function SystemSearchField({
  api,
  value,
  label = "Solar system",
  required = false,
  onChange,
}: {
  api: ApiClient;
  value: SystemSearchResult | null;
  label?: string;
  required?: boolean;
  onChange: (system: SystemSearchResult | null) => void;
}) {
  const [query, setQuery] = useState(value?.name ?? "");
  const [results, setResults] = useState<SystemSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const requestId = useRef(0);

  useEffect(() => setQuery(value?.name ?? ""), [value?.system_id, value?.name]);

  useEffect(() => {
    const cleaned = query.trim();
    if (value && cleaned === value.name) {
      setResults([]);
      return;
    }
    if (cleaned.length < 2) {
      setResults([]);
      return;
    }
    const current = ++requestId.current;
    const timer = window.setTimeout(async () => {
      setBusy(true);
      try {
        const rows = await api<SystemSearchResult[]>(`/events/search/systems?q=${encodeURIComponent(cleaned)}&limit=12`);
        if (requestId.current === current) {
          setResults(rows);
          setOpen(true);
        }
      } finally {
        if (requestId.current === current) setBusy(false);
      }
    }, 220);
    return () => window.clearTimeout(timer);
  }, [api, query, value]);

  return (
    <label className="event-system-field">
      <span>{label}</span>
      <div className="event-search-input">
        <Search size={16} />
        <input
          required={required}
          value={query}
          placeholder="Search by system name"
          onFocus={() => setOpen(results.length > 0)}
          onBlur={() => window.setTimeout(() => setOpen(false), 140)}
          onChange={(event) => {
            setQuery(event.target.value);
            if (value && event.target.value !== value.name) onChange(null);
          }}
        />
        {busy && <small>Searching…</small>}
      </div>
      {open && results.length > 0 && (
        <div className="event-search-results">
          {results.map((system) => (
            <button
              type="button"
              key={system.system_id}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange(system);
                setQuery(system.name);
                setOpen(false);
              }}
            >
              <strong>{system.name}</strong>
              <span>{system.security_status?.toFixed(1) ?? "?"} · {system.region_name ?? "Unknown region"}</span>
            </button>
          ))}
        </div>
      )}
    </label>
  );
}
