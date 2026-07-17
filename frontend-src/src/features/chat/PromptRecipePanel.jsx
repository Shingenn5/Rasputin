import React, { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, ChevronRight, Sparkles, X } from "lucide-react";
import { useFocusTrap } from "../../components/useFocusTrap.js";
import {
  buildRecipeObjective,
  initialRecipeValues,
  missingRecipeFields,
  recipesForMode,
} from "./promptRecipes.js";

export function PromptRecipePanel({
  modes,
  initialMode,
  initialRecipeId,
  returnFocusRef,
  onApply,
  onClose,
}) {
  const [mode, setMode] = useState(initialMode || "chat");
  const [selectedId, setSelectedId] = useState(initialRecipeId || null);
  const [values, setValues] = useState({});
  const [objective, setObjective] = useState("");
  const firstModeRef = useRef(null);
  const panelRef = useFocusTrap({
    active: true,
    onClose,
    initialFocusRef: firstModeRef,
    returnFocusRef,
  });

  useEffect(() => {
    setMode(initialMode || "chat");
    setSelectedId(initialRecipeId || null);
  }, [initialMode, initialRecipeId]);

  const recipes = useMemo(() => recipesForMode(mode), [mode]);
  const selected = recipes.find((item) => item.id === selectedId) || null;

  useEffect(() => {
    if (!selected) {
      setValues({});
      setObjective("");
      return;
    }
    const nextValues = initialRecipeValues(selected);
    setValues(nextValues);
    setObjective(buildRecipeObjective(selected, nextValues));
  }, [selected]);

  function chooseMode(nextMode) {
    setMode(nextMode);
    setSelectedId(null);
  }

  function chooseRecipe(item) {
    setSelectedId(item.id);
  }

  function updateField(fieldId, value) {
    const next = { ...values, [fieldId]: value };
    setValues(next);
    setObjective(buildRecipeObjective(selected, next));
  }

  const missing = missingRecipeFields(selected, values);
  const canApply = Boolean(selected) && missing.length === 0 && objective.trim().length > 0;

  return (
    <aside
      ref={panelRef}
      className="prompt-recipe-panel"
      data-testid="prompt-recipe-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby="promptRecipeTitle"
      tabIndex={-1}
    >
      <header className="prompt-recipe-head">
        <div>
          <span className="prompt-recipe-eyebrow"><Sparkles size={13} aria-hidden="true" /> Guided prompts</span>
          <h2 id="promptRecipeTitle">{selected ? selected.title : "Choose a recipe"}</h2>
          <p>{selected ? "Fill what you know, then edit the final objective before using it." : "Start from a proven job instead of a blank prompt."}</p>
        </div>
        <button type="button" className="icon-button" data-testid="prompt-recipe-close" aria-label="Close prompt recipes" onClick={onClose}>
          <X size={18} />
        </button>
      </header>

      {selected ? (
        <div className="prompt-recipe-editor">
          <button type="button" className="prompt-recipe-back" onClick={() => setSelectedId(null)}>
            <ArrowLeft size={14} aria-hidden="true" /> Back to {modes.find((item) => item.value === mode)?.label || mode} recipes
          </button>

          <div className="prompt-recipe-summary">
            <p>{selected.description}</p>
            <dl>
              <div><dt>Mode</dt><dd>{modes.find((item) => item.value === selected.mode)?.label || selected.mode}</dd></div>
              <div><dt>Reasoning</dt><dd>{selected.reasoning}</dd></div>
              <div><dt>Expected output</dt><dd>{selected.output}</dd></div>
            </dl>
          </div>

          <div className="prompt-recipe-fields">
            {selected.fields.map((itemField) => {
              const inputId = `prompt-recipe-${selected.id}-${itemField.id}`;
              const Input = itemField.multiline ? "textarea" : "input";
              return (
                <label key={itemField.id} htmlFor={inputId}>
                  <span>{itemField.label}{itemField.required ? <em>Required</em> : <small>Optional</small>}</span>
                  <Input
                    id={inputId}
                    data-testid={`prompt-recipe-field-${itemField.id}`}
                    value={values[itemField.id] || ""}
                    rows={itemField.multiline ? 3 : undefined}
                    placeholder={itemField.placeholder}
                    required={itemField.required}
                    onChange={(event) => updateField(itemField.id, event.target.value)}
                  />
                </label>
              );
            })}
          </div>

          <label className="prompt-recipe-preview" htmlFor="promptRecipeObjective">
            <span>Editable objective preview</span>
            <textarea
              id="promptRecipeObjective"
              data-testid="prompt-recipe-preview"
              rows={8}
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
            />
          </label>

          {missing.length > 0 && (
            <p className="prompt-recipe-validation" role="status">
              Complete {missing.map((itemField) => itemField.label).join(", ")} to use this recipe.
            </p>
          )}
        </div>
      ) : (
        <div className="prompt-recipe-browser">
          <div className="prompt-recipe-modes" aria-label="Recipe modes">
            {modes.map((item, index) => (
              <button
                key={item.value}
                ref={index === 0 ? firstModeRef : undefined}
                type="button"
                data-testid={`prompt-recipe-mode-${item.value}`}
                className={item.value === mode ? "is-active" : ""}
                aria-pressed={item.value === mode}
                onClick={() => chooseMode(item.value)}
              >
                {item.label}<small>{recipesForMode(item.value).length}</small>
              </button>
            ))}
          </div>

          <div className="prompt-recipe-list" aria-live="polite">
            {recipes.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="prompt-recipe-card"
                  data-testid="prompt-recipe-card"
                  onClick={() => chooseRecipe(item)}
                >
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.description}</small>
                  </span>
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              ))}
          </div>
        </div>
      )}

      <footer className="prompt-recipe-footer">
        {selected ? (
          <>
            <p>Nothing runs until you send the objective from the composer.</p>
            <button
              type="button"
              className="prompt-recipe-apply"
              data-testid="prompt-recipe-apply"
              disabled={!canApply}
              onClick={() => onApply({ recipe: selected, objective: objective.trim() })}
            >
              <Check size={15} aria-hidden="true" /> Use in composer
            </button>
          </>
        ) : (
          <p>Choose any recipe now. Rasputin checks model readiness when you send it.</p>
        )}
      </footer>
    </aside>
  );
}

export default PromptRecipePanel;
