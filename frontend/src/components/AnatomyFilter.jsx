import { useState, useEffect, useCallback, useRef } from "react";

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

export function AnatomyFilter({ value, onChange }) {
  const [inputVal, setInputVal] = useState(value || "");
  const [suggestions, setSuggestions] = useState([]);
  const skipNextFetchRef = useRef(false);
  const previousValueRef = useRef(value || "");

  const fetchSuggestions = useCallback(
    debounce(async (q) => {
      if (!q || q.length < 2) { setSuggestions([]); return; }
      try {
        const res = await fetch(`/api/anatomy/search?q=${encodeURIComponent(q)}`);
        setSuggestions(res.ok ? await res.json() : []);
      } catch {
        setSuggestions([]);
      }
    }, 300),
    []
  );

  useEffect(() => {
    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false;
      return;
    }
    fetchSuggestions(inputVal);
  }, [inputVal, fetchSuggestions]);

  // Sync external changes from URL/examples while avoiding a redundant autocomplete fetch.
  useEffect(() => {
    const nextValue = value || "";
    if (nextValue === previousValueRef.current) return;
    previousValueRef.current = nextValue;
    skipNextFetchRef.current = true;
    setSuggestions([]);
    setInputVal(nextValue);
  }, [value]);

  function select(term) {
    skipNextFetchRef.current = true;
    setInputVal(term);
    setSuggestions([]);
    onChange(term);
  }

  function clear() {
    skipNextFetchRef.current = false;
    setInputVal("");
    setSuggestions([]);
    onChange(null);
  }

  return (
    <div className="anatomy-filter">
      <label>Find genes by anatomy</label>
      <div className="anatomy-filter-row">
        <div className="anatomy-input-shell">
          <input
            className="anatomy-input"
            type="text"
            placeholder="e.g. hindbrain"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onBlur={() => setTimeout(() => setSuggestions([]), 150)}
            autoComplete="off"
          />
          {suggestions.length > 0 && (
            <div className="autocomplete-dropdown">
              {suggestions.map((s) => (
                <div
                  key={s}
                  className="autocomplete-item"
                  onMouseDown={() => select(s)}
                >
                  {s}
                </div>
              ))}
            </div>
          )}
          {inputVal && (
            <button className="anatomy-clear" title="Clear anatomy gene search" onClick={clear}>
              ×
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
