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
  const inputRef = useRef(null);

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
  }, [value]);

  function submit(symbol) {
    const s = symbol.trim();
    if (!s) return;
    onAdd(s);
    setValue("");
    setSuggestions([]);
  }

  function handleKeyDown(e) {
    if (e.key === "ArrowDown") {
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        submit(suggestions[activeIdx]);
      } else {
        submit(value);
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
        />
        <button className="gene-input-btn" onClick={() => submit(value)}>
          Add
        </button>
        {suggestions.length > 0 && (
          <div className="autocomplete-dropdown">
            {suggestions.map((s, i) => (
              <div
                key={s}
                className={`autocomplete-item${i === activeIdx ? " active" : ""}`}
                onMouseDown={() => submit(s)}
              >
                {s}
              </div>
            ))}
          </div>
        )}
      </div>
      <p className="field-helper">
        Press Enter to add — compare genes side by side
      </p>
    </div>
  );
}
