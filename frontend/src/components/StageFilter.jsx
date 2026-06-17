import { useEffect, useState } from "react";

const FALLBACK_STAGES = [
  { stage_name: "Gastrula:50%-epiboly", begin_hours: 5.25, display_label: "50%-epiboly" },
  { stage_name: "Gastrula:Germ-ring", begin_hours: 5.67, display_label: "Germ-ring" },
  { stage_name: "Segmentation:1-4 somites", begin_hours: 10.33, display_label: "1-4 somites" },
  { stage_name: "Segmentation:14-19 somites", begin_hours: 16, display_label: "14-19 somites" },
  { stage_name: "Segmentation:20-25 somites", begin_hours: 19, display_label: "20-25 somites" },
  { stage_name: "Pharyngula:Prim-15", begin_hours: 30, display_label: "Prim-15 (30 hpf)" },
  { stage_name: "Pharyngula:High-pec", begin_hours: 42, display_label: "High-pec (42 hpf)" },
  { stage_name: "Hatching:Long-pec", begin_hours: 48, display_label: "Long-pec (48 hpf)" },
  { stage_name: "Larval:Day 5", begin_hours: 120, display_label: "Day 5 (120 hpf)" },
];

function shortStageLabel(stage) {
  return stage.display_label || stage.stage_name.split(":").pop();
}

function fullStageLabel(stage) {
  if (!stage.display_label) {
    return stage.stage_name;
  }

  const [stageGroup, stageName] = stage.stage_name.split(":");
  if (stageName && stage.display_label.startsWith(stageName)) {
    return `${stageGroup}:${stage.display_label}`;
  }
  if (stage.stage_name.includes(stage.display_label)) {
    return stage.stage_name;
  }
  return `${stage.stage_name} (${stage.display_label})`;
}

export function StageFilter({ stageMin, stageMax, onChange }) {
  const [stages, setStages] = useState(FALLBACK_STAGES);

  useEffect(() => {
    fetch("/api/stages")
      .then((r) => r.ok ? r.json() : FALLBACK_STAGES)
      .then((items) => {
        if (Array.isArray(items) && items.length > 0) setStages(items);
      })
      .catch(() => {});
  }, []);

  const minHours = stages[0].begin_hours;
  const maxHours = stages[stages.length - 1].begin_hours;

  const selectedMin = stageMin ?? minHours;
  const selectedMax = stageMax ?? maxHours;
  const selectedMinStage = stages.find((s) => s.begin_hours === selectedMin);
  const selectedMaxStage = stages.find((s) => s.begin_hours === selectedMax);

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
      <div className="stage-filter-selects">
        <label className="stage-select-field">
          <span className="field-label">Developmental stage</span>
          <select
            value={selectedMin}
            onChange={handleMin}
            title={selectedMinStage ? fullStageLabel(selectedMinStage) : undefined}
          >
            {stages.map((s) => (
              <option key={s.begin_hours} value={s.begin_hours} title={fullStageLabel(s)}>
                {shortStageLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <span className="range-arrow" aria-hidden="true">→</span>
        <label className="stage-select-field">
          <span className="field-label">Time point</span>
          <select
            value={selectedMax}
            onChange={handleMax}
            title={selectedMaxStage ? fullStageLabel(selectedMaxStage) : undefined}
          >
            {stages.map((s) => (
              <option key={s.begin_hours} value={s.begin_hours} title={fullStageLabel(s)}>
                {shortStageLabel(s)}
              </option>
            ))}
          </select>
        </label>
        {isFiltered && (
          <button
            className="stage-clear"
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
