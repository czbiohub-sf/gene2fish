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
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef(null);
  const blurTimeoutRef = useRef(null);
  const previousValueRef = useRef(selectedTermsKey);

  const fetchSuggestions = useCallback(
    debounce(async (q) => {
      try {
        const res = await fetch(`/api/anatomy/search?q=${encodeURIComponent(q)}&limit=250`);
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

  useEffect(() => () => {
    if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
  }, []);

  const availableSuggestions = suggestions.filter(
    (suggestion) => !selectedTerms.some(
      (selected) => selected.toLowerCase() === suggestion.toLowerCase()
    )
  );

  // Sync external changes from URL/examples while avoiding a redundant autocomplete fetch.
  useEffect(() => {
    const nextValue = selectedTermsKey;
    if (nextValue === previousValueRef.current) return;
    previousValueRef.current = nextValue;
    setSuggestions([]);
    setInputVal("");
    setIsOpen(false);
  }, [selectedTermsKey]);

  function select(term) {
    if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
    setInputVal("");
    setSuggestions([]);
    setIsOpen(false);
    if (selectedTerms.some((selected) => selected.toLowerCase() === term.toLowerCase())) {
      return;
    }
    onChange([...selectedTerms, term]);
  }

  function remove(term) {
    onChange(selectedTerms.filter((selected) => selected !== term));
  }

  function clear() {
    if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
    setInputVal("");
    setSuggestions([]);
    setIsOpen(false);
    onChange([]);
  }

  function toggleDropdown() {
    if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
    setIsOpen((current) => {
      const next = !current;
      if (next) {
        inputRef.current?.focus();
        fetchSuggestions(inputVal);
      } else {
        inputRef.current?.blur();
      }
      return next;
    });
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
            ref={inputRef}
            className="anatomy-input"
            type="text"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={isOpen && availableSuggestions.length > 0}
            aria-controls="anatomy-options"
            placeholder="e.g. hindbrain"
            value={inputVal}
            onChange={(e) => {
              if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
              setInputVal(e.target.value);
              setIsOpen(true);
            }}
            onFocus={() => {
              if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
              setIsOpen(true);
            }}
            onBlur={() => {
              blurTimeoutRef.current = setTimeout(() => setIsOpen(false), 150);
            }}
            autoComplete="off"
          />
          <button
            className="anatomy-dropdown-toggle"
            type="button"
            title="Show anatomy options"
            aria-label="Show anatomy options"
            aria-expanded={isOpen && availableSuggestions.length > 0}
            onClick={toggleDropdown}
          >
            ▾
          </button>
          {isOpen && availableSuggestions.length > 0 && (
            <div id="anatomy-options" className="autocomplete-dropdown" role="listbox">
              {availableSuggestions.map((s) => (
                <div
                  key={s}
                  className="autocomplete-item"
                  role="option"
                  aria-selected="false"
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
