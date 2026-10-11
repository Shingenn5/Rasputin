import { useState } from "react";
import { Play } from "lucide-react";

export function PlannerTab({ models, createTask }) {
  const [objective, setObjective] = useState("");
  const [model, setModel] = useState("dry-run");
  const [skill, setSkill] = useState("general");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!objective.trim()) return;
    createTask({ objective, model, skill, mode: "agent" });
    setObjective("");
  };

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div className="w2-card">
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Mission Planner</h3>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
            Objective
            <textarea className="w2-input" rows={4} value={objective} onChange={e => setObjective(e.target.value)} required placeholder="What should the agent accomplish?" />
          </label>
          <div style={{ display: "flex", gap: "12px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
              Model
              <select className="w2-input" value={model} onChange={e => setModel(e.target.value)}>
                <option value="dry-run">Dry Run (No inference)</option>
                {models?.filter(m => m.key !== "local-embeddings").map(m => (
                  <option key={m.key} value={m.key}>{m.name}</option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
              Skill / Role
              <select className="w2-input" value={skill} onChange={e => setSkill(e.target.value)}>
                <option value="general">General AI</option>
                <option value="coder">Software Engineer</option>
                <option value="researcher">Researcher</option>
              </select>
            </label>
          </div>
          <button className="w2-button primary" type="submit" disabled={!objective.trim()} style={{ alignSelf: "flex-start" }}>
            <Play size={14} /> Launch Mission
          </button>
        </form>
      </div>
    </div>
  );
}
