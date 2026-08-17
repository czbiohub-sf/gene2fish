import { useState, useEffect, useCallback, useRef } from "react";

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

const NO_IMAGES_HINT = "No images for the genes in the comparison";

// Classify an anatomy suggestion against the current gene set's facets.
// `facets` null (no genes in the grid) means "no constraint" — everything
// stays enabled. Otherwise a term is disabled unless at least one current gene
// expresses it, and its image count guides selection.
function anatomyOptionState(term, facets) {
  if (!facets) return { disabled: false, count: null };
  const count = facets[term.toLowerCase()] || 0;
  return { disabled: count === 0, count };
}

export function AnatomyFilter({ value, onChange, anatomyFacets }) {
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

  // Enabled options surface above disabled ones so users don't scan past
  // unusable terms. Both groups stay alphabetical — the API's order, restated
  // here because the segmentation would otherwise interleave them again.
  const orderedSuggestions = availableSuggestions
    .map((term) => ({ term, ...anatomyOptionState(term, anatomyFacets) }))
    .sort(
      (a, b) =>
        (a.disabled ? 1 : 0) - (b.disabled ? 1 : 0)
        || a.term.toLowerCase().localeCompare(b.term.toLowerCase())
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
                  <span className="anatomy-term-chip" title={term}>
                    <span className="anatomy-term-chip-text">{term}</span>
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
              {orderedSuggestions.map(({ term, disabled, count }) => (
                <div
                  key={term}
                  className={`autocomplete-item${disabled ? " disabled" : ""}`}
                  title={disabled ? NO_IMAGES_HINT : term}
                  role="option"
                  aria-selected="false"
                  aria-disabled={disabled || undefined}
                  onMouseDown={disabled ? undefined : () => select(term)}
                >
                  <span className="autocomplete-item-label">{term}</span>
                  {count != null && count > 0 && (
                    <span className="autocomplete-count">{count}</span>
                  )}
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
