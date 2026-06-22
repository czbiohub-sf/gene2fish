import { useState, useEffect, useRef, useCallback } from "react";

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

export function GeneInput({ onAdd }) {
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  // Validation is async, so a slow response must not mutate state for a symbol
  // the user has moved on from. Each validation captures the current sequence
  // number; only the latest one may touch state, and the previous request is
  // aborted outright.
  const requestSeqRef = useRef(0);
  const abortRef = useRef(null);

  function cancelInFlight() {
    requestSeqRef.current += 1; // any pending response is now stale
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }

  const fetchSuggestions = useCallback(
    debounce(async (q) => {
      if (!q) { setSuggestions([]); return; }
      try {
        const res = await fetch(`/api/genes/search?q=${encodeURIComponent(q)}`);
        if (res.ok) setSuggestions(await res.json());
      } catch {
        setSuggestions([]);
      }
    }, 300),
    []
  );

  useEffect(() => {
    fetchSuggestions(value);
    setActiveIdx(-1);
    setError(null);
    // Typing supersedes any in-flight validation so a late response can't add
    // the previous symbol or clear the input the user is now editing.
    cancelInFlight();
    setValidating(false);
  }, [value]);

  // Abort a pending validation if the component unmounts mid-request.
  useEffect(() => () => cancelInFlight(), []);

  function reset() {
    setValue("");
    setSuggestions([]);
    setError(null);
  }

  // Adds a symbol that is already known to be valid (picked from the
  // autocomplete, which only surfaces real genes).
  function addValidated(symbol) {
    const s = symbol.trim();
    if (!s) return;
    onAdd(s);
    reset();
  }

  // Validates a free-typed entry against the dataset before opening a column,
  // so an invalid or nonsensical name is rejected instead of creating an empty
  // column. Resolves to the canonical symbol (e.g. "OCT4" → "pou5f3").
  async function submitTyped(symbol) {
    const s = symbol.trim();
    if (!s || validating) return;
    // Supersede anything already pending, then claim this request's sequence.
    cancelInFlight();
    const seq = requestSeqRef.current;
    const controller = new AbortController();
    abortRef.current = controller;
    setValidating(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/genes/${encodeURIComponent(s)}/resolve`,
        { signal: controller.signal }
      );
      if (seq !== requestSeqRef.current) return; // a newer request superseded us
      if (res.ok) {
        const { symbol: canonical } = await res.json();
        if (seq !== requestSeqRef.current) return;
        onAdd(canonical);
        reset();
      } else if (res.status === 404) {
        setError(`No gene matching "${s}". Pick a suggestion from the list.`);
      } else {
        setError("Couldn't validate that gene. Please try again.");
      }
    } catch (err) {
      if (err.name === "AbortError" || seq !== requestSeqRef.current) return;
      setError("Couldn't validate that gene. Check your connection.");
    } finally {
      if (seq === requestSeqRef.current) {
        setValidating(false);
        abortRef.current = null;
      }
    }
  }

  function handleKeyDown(e) {
    if (e.key === "ArrowDown") {
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        addValidated(suggestions[activeIdx].symbol);
      } else {
        submitTyped(value);
      }
    } else if (e.key === "Escape") {
      setSuggestions([]);
    }
  }

  return (
    <div className="gene-input-wrapper">
      <label className="field-label" htmlFor="gene-symbol-input">
        Search gene
      </label>
      <div className="gene-input-row">
        <input
          id="gene-symbol-input"
          ref={inputRef}
          className="gene-input"
          type="text"
          placeholder="Gene symbol (e.g. pax2a)"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => setTimeout(() => setSuggestions([]), 150)}
          autoComplete="off"
          spellCheck={false}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "gene-input-error" : undefined}
        />
        <button
          className="gene-input-btn"
          onClick={() => submitTyped(value)}
          disabled={validating}
        >
          {validating ? "Checking…" : "Add"}
        </button>
        {suggestions.length > 0 && (
          <div className="autocomplete-dropdown">
            {suggestions.map((s, i) => (
              <div
                key={s.symbol}
                className={`autocomplete-item${i === activeIdx ? " active" : ""}`}
                onMouseDown={() => addValidated(s.symbol)}
              >
                {s.symbol}
                {s.matched_alias && (
                  <span className="autocomplete-alias">a.k.a. {s.matched_alias}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {error ? (
        <p id="gene-input-error" className="field-error" role="alert">
          {error}
        </p>
      ) : (
        <p className="field-helper">
          Press Enter to add — compare genes side by side
        </p>
      )}
    </div>
  );
}
