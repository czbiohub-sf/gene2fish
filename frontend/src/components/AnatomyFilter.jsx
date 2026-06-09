import { useState, useEffect, useCallback, useRef } from "react";

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

export function AnatomyFilter({ value, onChange }) {
  const selectedTerms = Array.isArray(value) ? value : (value ? [value] : []);
  const selectedTermsKey = selectedTerms.join("\n");
  const [inputVal, setInputVal] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const previousValueRef = useRef(selectedTermsKey);

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
    fetchSuggestions(inputVal);
  }, [inputVal, fetchSuggestions]);

  // Sync external changes from URL/examples while avoiding a redundant autocomplete fetch.
  useEffect(() => {
    const nextValue = selectedTermsKey;
    if (nextValue === previousValueRef.current) return;
    previousValueRef.current = nextValue;
    setSuggestions([]);
    setInputVal("");
  }, [selectedTermsKey]);

  function select(term) {
    setInputVal("");
    setSuggestions([]);
    if (selectedTerms.some((selected) => selected.toLowerCase() === term.toLowerCase())) {
      return;
    }
    onChange([...selectedTerms, term]);
  }

  function remove(term) {
    onChange(selectedTerms.filter((selected) => selected !== term));
  }

  function clear() {
    setInputVal("");
    setSuggestions([]);
    onChange([]);
  }

  return (
    <div className="anatomy-filter">
      <label>Find genes by anatomy</label>
      <div className="anatomy-filter-row">
        <div className="anatomy-input-shell">
          {selectedTerms.length > 0 && (
            <div className="anatomy-selected-terms" aria-label="Selected anatomy terms">
              {selectedTerms.map((term, index) => (
                <span key={term} className="anatomy-selected-term">
                  {index > 0 && <span className="anatomy-and" aria-hidden="true">AND</span>}
                  <span className="anatomy-term-chip">
                    {term}
                    <button
                      type="button"
                      className="anatomy-term-remove"
                      title={`Remove ${term}`}
                      onClick={() => remove(term)}
                    >
                      ×
                    </button>
                  </span>
                </span>
              ))}
            </div>
          )}
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
          {(inputVal || selectedTerms.length > 0) && (
            <button className="anatomy-clear" title="Clear anatomy gene search" onClick={clear}>
              ×
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
