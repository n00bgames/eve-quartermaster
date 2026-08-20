import { Search, X } from "lucide-react";

import "./moduleFinder.css";

type ModuleFinderProps = {
  query: string;
  onQueryChange: (query: string) => void;
  placeholder: string;
  label?: string;
  resultCount?: number;
  totalCount?: number;
};

export function ModuleFinder({
  query,
  onQueryChange,
  placeholder,
  label = "Search records",
  resultCount,
  totalCount,
}: ModuleFinderProps) {
  const showCount = resultCount != null && totalCount != null;

  return (
    <div className="module-finder">
      <label>
        <span className="sr-only">{label}</span>
        <Search size={17} aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder={placeholder}
          aria-label={label}
        />
        {query && (
          <button type="button" className="module-finder-clear" onClick={() => onQueryChange("")} title="Clear search" aria-label="Clear search">
            <X size={15} />
          </button>
        )}
      </label>
      {showCount && <small>{resultCount.toLocaleString()} of {totalCount.toLocaleString()} shown</small>}
    </div>
  );
}

