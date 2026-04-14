import { useEffect, useState } from "react";

export function StageFilter({ stageMin, stageMax, onChange }) {
  const [stages, setStages] = useState([]);

  useEffect(() => {
    fetch("/api/stages")
      .then((r) => r.json())
      .then(setStages)
      .catch(() => {});
  }, []);

  if (stages.length === 0) return null;

  const minHours = stages[0].begin_hours;
  const maxHours = stages[stages.length - 1].begin_hours;

  const selectedMin = stageMin ?? minHours;
  const selectedMax = stageMax ?? maxHours;

  function handleMin(e) {
    const val = parseFloat(e.target.value);
    onChange(val <= selectedMax ? val : selectedMax, selectedMax);
  }

  function handleMax(e) {
    const val = parseFloat(e.target.value);
    onChange(selectedMin, val >= selectedMin ? val : selectedMin);
  }

  const isFiltered = selectedMin !== minHours || selectedMax !== maxHours;

  return (
    <div className="stage-filter">
      <label>Developmental stage</label>
      <div className="stage-filter-selects">
        <select value={selectedMin} onChange={handleMin}>
          {stages.map((s) => (
            <option key={s.begin_hours} value={s.begin_hours}>
              {s.display_label}
            </option>
          ))}
        </select>
        <span>→</span>
        <select value={selectedMax} onChange={handleMax}>
          {stages.map((s) => (
            <option key={s.begin_hours} value={s.begin_hours}>
              {s.display_label}
            </option>
          ))}
        </select>
        {isFiltered && (
          <button
            className="anatomy-clear"
            title="Reset stage filter"
            onClick={() => onChange(null, null)}
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}
