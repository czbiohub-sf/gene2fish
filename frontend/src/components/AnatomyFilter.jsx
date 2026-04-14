import { useState, useEffect, useCallback } from "react";

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

  const fetchSuggestions = useCallback(
    debounce(async (q) => {
      if (!q || q.length < 2) { setSuggestions([]); return; }
      try {
        const res = await fetch(`/api/anatomy/search?q=${encodeURIComponent(q)}`);
        if (res.ok) setSuggestions(await res.json());
      } catch {
        setSuggestions([]);
      }
    }, 300),
    []
  );

  useEffect(() => {
    fetchSuggestions(inputVal);
  }, [inputVal]);

  // Sync external clear
  useEffect(() => {
    if (!value) setInputVal("");
  }, [value]);

  function select(term) {
    setInputVal(term);
    setSuggestions([]);
    onChange(term);
  }

  function clear() {
    setInputVal("");
    setSuggestions([]);
    onChange(null);
  }

  return (
    <div className="anatomy-filter">
      <label>Anatomy</label>
      <div className="anatomy-filter-row">
        <div style={{ position: "relative" }}>
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
        </div>
        {inputVal && (
          <button className="anatomy-clear" title="Clear anatomy filter" onClick={clear}>
            ×
          </button>
        )}
      </div>
    </div>
  );
}
