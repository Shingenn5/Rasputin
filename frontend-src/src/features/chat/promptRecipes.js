export const RECIPE_MODES = ["chat", "analyze", "research", "code", "write", "organize", "review"];

const field = (id, label, placeholder, required = false, multiline = false) => ({
  id,
  label,
  placeholder,
  required,
  multiline,
});

const recipe = (mode, id, title, description, prompt, fields = [], options = {}) => ({
  id,
  mode,
  title,
  description,
  prompt,
  fields,
  reasoning: options.reasoning || "auto",
  output: options.output || "A clear response in the chat",
  requiresAgentic: options.requiresAgentic ?? mode !== "chat",
  requiresWeb: Boolean(options.requiresWeb),
  featured: Boolean(options.featured),
});

export const PROMPT_RECIPES = [
  recipe("chat", "brainstorm", "Brainstorm ideas", "Generate and organize possibilities before choosing a direction.",
    "Brainstorm practical ideas for this goal:\n\n{{goal}}\n\nConsider constraints, tradeoffs, and a few unconventional options. Group the strongest ideas and recommend the best next step.",
    [field("goal", "Goal or problem", "What are you trying to accomplish?", true, true)],
    { reasoning: "medium", featured: true }),
  recipe("chat", "make-decision", "Make a decision", "Compare options and reach a defensible recommendation.",
    "Help me decide between these options:\n\n{{options}}\n\nDecision criteria: {{criteria}}\n\nCompare the tradeoffs, identify missing information, and recommend one option with clear reasoning.",
    [field("options", "Options", "List the choices you are considering.", true, true), field("criteria", "Decision criteria", "Cost, speed, risk, maintainability...", false, true)],
    { reasoning: "high", output: "A comparison and recommendation" }),
  recipe("chat", "explain-topic", "Explain a topic", "Get a clear explanation calibrated to your background.",
    "Explain {{topic}} for someone with this background: {{background}}. Start with the intuition, then give a concrete example, common mistakes, and the most useful next concept to learn.",
    [field("topic", "Topic", "What should Rasputin explain?", true), field("background", "Your background", "Beginner, experienced developer, domain expert...", false)],
    { reasoning: "medium" }),
  recipe("chat", "plan-project", "Plan a project", "Turn an objective into milestones, risks, and first actions.",
    "Create a practical project plan for:\n\n{{objective}}\n\nConstraints: {{constraints}}\n\nDefine the outcome, milestones, dependencies, risks, acceptance checks, and the first three actions.",
    [field("objective", "Project objective", "Describe the result you want.", true, true), field("constraints", "Constraints", "Deadline, budget, people, technology...", false, true)],
    { reasoning: "high", output: "A milestone-based project plan" }),
  recipe("chat", "improve-prompt", "Improve a prompt", "Rewrite a rough request into a precise, reusable prompt.",
    "Improve the following prompt without changing its intent:\n\n{{draft}}\n\nMake the objective, context, constraints, output format, and acceptance criteria explicit. Return the improved prompt first, followed by a short explanation of the changes.",
    [field("draft", "Rough prompt", "Paste the prompt you want to improve.", true, true)],
    { reasoning: "low", output: "A reusable prompt and change notes" }),

  recipe("analyze", "summarize-workspace", "Summarize the workspace", "Map the active workspace and highlight what matters most.",
    "Analyze the active workspace. Summarize its purpose, major areas, important files, current state, obvious risks, and the most useful next actions. Cite workspace evidence for material claims.\n\nFocus: {{focus}}",
    [field("focus", "Optional focus", "Architecture, project status, documentation, risks...", false)],
    { reasoning: "medium", output: "An evidence-grounded workspace brief", featured: true }),
  recipe("analyze", "compare-documents", "Compare documents", "Find agreements, differences, omissions, and contradictions.",
    "Compare these documents or paths: {{documents}}\n\nFocus on: {{focus}}\n\nProduce a structured comparison of shared claims, meaningful differences, contradictions, missing information, and recommended follow-up. Cite the source for every important finding.",
    [field("documents", "Documents or paths", "List filenames, paths, or attached documents.", true, true), field("focus", "Comparison focus", "Policy differences, requirements, numbers, decisions...", false)],
    { reasoning: "high", output: "A cited comparison" }),
  recipe("analyze", "extract-decisions", "Extract decisions and actions", "Turn notes or project material into an accountable action register.",
    "Review {{source}} and extract decisions, unresolved questions, action items, owners, deadlines, dependencies, and risks. Distinguish confirmed facts from inference and cite the supporting evidence.",
    [field("source", "Source material", "A file, folder, meeting notes, or attached documents.", true, true)],
    { reasoning: "medium", output: "A decision and action register" }),
  recipe("analyze", "inspect-dataset", "Inspect a dataset", "Profile a file and surface quality issues or patterns.",
    "Inspect the dataset at {{dataset}}. Describe its structure, key fields, missing or inconsistent data, notable distributions, suspicious values, and promising questions for deeper analysis. Do not modify the source.",
    [field("dataset", "Dataset path or attachment", "CSV, spreadsheet, JSON, or similar data.", true)],
    { reasoning: "high", output: "A data quality and exploration report" }),
  recipe("analyze", "find-contradictions", "Find contradictions", "Locate incompatible claims across workspace evidence.",
    "Search the active workspace for contradictions or stale claims about {{topic}}. Show each conflicting statement with its source, explain whether the conflict is real or contextual, and recommend which source should be treated as authoritative.",
    [field("topic", "Topic or claim", "What should Rasputin verify?", true)],
    { reasoning: "high", output: "A cited contradiction audit" }),

  recipe("research", "deep-dive", "Deep-dive a topic", "Build an evidence-backed understanding of a focused question.",
    "Research this question thoroughly: {{question}}\n\nScope and constraints: {{scope}}\n\nDevelop a research plan, gather relevant evidence through approved tools, compare credible perspectives, identify uncertainty, and produce a cited synthesis with practical conclusions.",
    [field("question", "Research question", "What do you need to understand?", true, true), field("scope", "Scope or constraints", "Geography, time period, sources, exclusions...", false, true)],
    { reasoning: "high", requiresWeb: true, output: "A cited research brief", featured: true }),
  recipe("research", "latest-sources", "Find latest references", "Locate recent authoritative material and explain what changed.",
    "Find the most recent authoritative references about {{topic}}. Prioritize primary sources, record publication dates, distinguish event dates from article dates, summarize the current state, and flag anything that changed recently.",
    [field("topic", "Topic", "What needs current information?", true)],
    { reasoning: "medium", requiresWeb: true, output: "A dated source list and current-state summary" }),
  recipe("research", "vendor-comparison", "Compare vendors or products", "Evaluate alternatives against explicit requirements.",
    "Research and compare these options: {{options}}\n\nRequirements: {{requirements}}\n\nUse current primary sources where possible. Compare fit, limitations, operational burden, cost signals, privacy, and implementation risk. Recommend a shortlist and identify what still needs validation.",
    [field("options", "Options", "Products, vendors, models, or approaches.", true, true), field("requirements", "Requirements", "Must-haves, constraints, budget, environment...", true, true)],
    { reasoning: "high", requiresWeb: true, output: "A sourced comparison and shortlist" }),
  recipe("research", "evidence-matrix", "Build an evidence matrix", "Map claims to supporting and conflicting sources.",
    "Build an evidence matrix for {{question}}. For each material claim, list supporting evidence, conflicting evidence, source quality, date, confidence, and the implication for the final conclusion.",
    [field("question", "Question or hypothesis", "What claim should the evidence test?", true, true)],
    { reasoning: "high", requiresWeb: true, output: "A claim-by-source evidence matrix" }),
  recipe("research", "literature-review", "Review a body of literature", "Synthesize themes, methods, gaps, and disagreements.",
    "Conduct a focused literature review on {{topic}}. Scope: {{scope}}. Group sources by theme or methodology, compare findings, identify consensus and disagreement, assess limitations, and propose the most important unanswered questions.",
    [field("topic", "Topic", "Research area or question.", true), field("scope", "Scope", "Years, disciplines, source types, exclusions...", false, true)],
    { reasoning: "high", requiresWeb: true, output: "A structured literature review" }),

  recipe("code", "fix-bug", "Fix a bug", "Investigate a defect, patch it, and run the configured checks.",
    "Fix this bug in the active workspace:\n\n{{problem}}\n\nExpected behavior: {{expected}}\nConstraints: {{constraints}}\n\nReproduce or trace the cause, make the smallest safe change, run the configured tests or checks, iterate on failures, and leave a reviewable summary of files changed and evidence.",
    [field("problem", "Bug or failing behavior", "Include errors, reproduction steps, or symptoms.", true, true), field("expected", "Expected behavior", "What should happen instead?", false, true), field("constraints", "Constraints", "Files to avoid, compatibility, performance...", false, true)],
    { reasoning: "high", output: "A tested, reviewable patch", featured: true }),
  recipe("code", "add-feature", "Add a feature", "Implement a scoped capability with tests and a review summary.",
    "Implement this feature in the active workspace:\n\n{{feature}}\n\nAcceptance criteria:\n{{acceptance}}\n\nInspect the existing design, match surrounding patterns, avoid unrelated refactors, add or update tests, run configured checks, and summarize the implementation and remaining risks.",
    [field("feature", "Feature request", "Describe the user-facing outcome.", true, true), field("acceptance", "Acceptance criteria", "What proves the feature is complete?", true, true)],
    { reasoning: "high", output: "An implemented feature with verification" }),
  recipe("code", "explain-repository", "Explain a repository", "Create a practical map of an unfamiliar codebase.",
    "Explain the active repository as an owner's guide. Cover startup paths, major directories, data flow, important abstractions, configuration, tests, deployment modes, and the safest places to make common changes. Cite files for every architectural claim.\n\nFocus: {{focus}}",
    [field("focus", "Optional focus", "Frontend, backend, model runtime, security...", false)],
    { reasoning: "medium", output: "A file-cited repository guide" }),
  recipe("code", "write-tests", "Write or improve tests", "Add focused coverage for a behavior or regression.",
    "Add or improve tests for: {{behavior}}\n\nInspect the current test patterns, cover the important success and failure paths, avoid brittle implementation-detail assertions, run the relevant suite, and report exactly what the tests prove.",
    [field("behavior", "Behavior to test", "Feature, bug regression, function, or workflow.", true, true)],
    { reasoning: "high", output: "Focused tests with passing evidence" }),
  recipe("code", "review-diff", "Review current changes", "Assess the working tree like a pull request reviewer.",
    "Review the current workspace changes. Identify correctness bugs, regressions, security issues, missing tests, and maintainability risks. Prioritize actionable findings with exact file and line references. Do not modify files unless I ask after the review.",
    [],
    { reasoning: "high", output: "A prioritized code review" }),

  recipe("write", "draft-report", "Draft a report", "Turn evidence and goals into a structured professional report.",
    "Draft a professional report about {{topic}} for {{audience}}. Purpose: {{purpose}}. Use available workspace evidence, distinguish facts from recommendations, and organize the result with an executive summary, findings, implications, and next actions.",
    [field("topic", "Report topic", "What should the report cover?", true), field("audience", "Audience", "Owner, technical team, executives, customers...", true), field("purpose", "Purpose", "Inform, recommend, document, persuade...", false, true)],
    { reasoning: "medium", output: "A structured report draft", featured: true }),
  recipe("write", "create-sop", "Create an SOP", "Document a repeatable process with checks and ownership.",
    "Create a standard operating procedure for {{process}}. Audience: {{audience}}. Include purpose, prerequisites, roles, numbered steps, decision points, safety notes, verification, rollback or escalation, and a completion checklist.",
    [field("process", "Process", "What repeatable work should the SOP cover?", true, true), field("audience", "Audience", "Who will follow it?", false)],
    { reasoning: "medium", output: "An operator-ready SOP" }),
  recipe("write", "prepare-proposal", "Prepare a proposal", "Frame a problem, solution, plan, value, and decision request.",
    "Draft a proposal for {{proposal}} aimed at {{audience}}. Include the problem, proposed solution, alternatives considered, scope, implementation plan, risks, expected value, success measures, and the decision or support required.",
    [field("proposal", "Proposal", "What are you proposing?", true, true), field("audience", "Audience", "Who must approve or support it?", true)],
    { reasoning: "high", output: "A decision-oriented proposal" }),
  recipe("write", "notes-to-brief", "Turn notes into a brief", "Convert rough material into a concise, coherent document.",
    "Turn the following notes or workspace source into a concise brief:\n\n{{source}}\n\nPreserve important qualifiers, remove repetition, surface decisions and risks, and end with clear next actions. Audience: {{audience}}.",
    [field("source", "Notes or source", "Paste notes or reference workspace paths.", true, true), field("audience", "Audience", "Who will read the brief?", false)],
    { reasoning: "low", output: "A concise briefing document" }),
  recipe("write", "rewrite-audience", "Rewrite for an audience", "Adapt tone, structure, and detail without losing meaning.",
    "Rewrite {{source}} for {{audience}}. Desired tone: {{tone}}. Preserve factual meaning and important caveats, improve clarity and flow, and call out any ambiguity that cannot be resolved from the source.",
    [field("source", "Source text or path", "Paste text or identify the document.", true, true), field("audience", "Target audience", "Executives, customers, beginners, specialists...", true), field("tone", "Tone", "Direct, formal, friendly, technical...", false)],
    { reasoning: "low", output: "An audience-calibrated rewrite" }),

  recipe("organize", "plan-cleanup", "Plan a folder cleanup", "Preview a safe organization plan before any changes.",
    "Analyze {{location}} and propose a safe folder cleanup plan. Identify clutter, duplicates, inconsistent naming, stale material, and risky moves. Show the proposed structure and mutation preview, but do not change anything until I approve.",
    [field("location", "Folder or workspace area", "Path or description of what to organize.", true)],
    { reasoning: "medium", output: "A previewable cleanup plan", featured: true }),
  recipe("organize", "find-duplicates", "Find duplicate files", "Identify exact and likely duplicates without deleting anything.",
    "Inspect {{location}} for exact and likely duplicate files. Group matches, explain the evidence, identify the safest canonical copy, and propose a review plan. Do not delete or move files.",
    [field("location", "Folder or workspace area", "Where should Rasputin search?", true)],
    { reasoning: "medium", output: "A duplicate review report" }),
  recipe("organize", "rename-consistently", "Create a rename plan", "Standardize names with a reversible preview.",
    "Create a consistent rename plan for {{location}} using this convention: {{convention}}. Show current and proposed paths, collisions, references that may break, and rollback steps. Do not rename anything until approved.",
    [field("location", "Folder or files", "What should be renamed?", true), field("convention", "Naming convention", "Desired pattern or rules.", true)],
    { reasoning: "high", output: "A collision-checked rename preview" }),
  recipe("organize", "archive-project", "Prepare a project archive", "Identify what to preserve and produce an archive plan.",
    "Prepare an archive plan for {{project}}. Identify essential source, documentation, decisions, deliverables, credentials or secrets that must not be copied, generated files that can be rebuilt, retention needs, and a verification checklist.",
    [field("project", "Project or folder", "What should be archived?", true)],
    { reasoning: "medium", output: "A verified archive plan" }),
  recipe("organize", "classify-documents", "Classify documents", "Group files by purpose, sensitivity, owner, or lifecycle.",
    "Classify documents in {{location}} using these categories or goals: {{categories}}. Explain uncertain classifications, flag sensitive material, and propose folders or metadata without moving files until approved.",
    [field("location", "Folder or workspace area", "Where are the documents?", true), field("categories", "Categories or goal", "Topic, sensitivity, lifecycle, department...", true, true)],
    { reasoning: "medium", output: "A reviewable classification plan" }),

  recipe("review", "review-artifact", "Review an artifact", "Assess a deliverable for correctness, clarity, and readiness.",
    "Review {{artifact}} for {{goal}}. Check factual support, structure, clarity, completeness, audience fit, internal consistency, and actionable risks. Separate required corrections from optional polish and cite the exact location of each issue.",
    [field("artifact", "Artifact or path", "What should Rasputin review?", true), field("goal", "Review goal", "Publication readiness, technical accuracy, executive clarity...", false)],
    { reasoning: "high", output: "A prioritized review", featured: true }),
  recipe("review", "audit-patch", "Audit a code patch", "Review changed code for defects and missing verification.",
    "Audit the current code changes. Look for correctness issues, regressions, unsafe behavior, permission mistakes, missing edge cases, and inadequate tests. Return only actionable findings with file and line references, ordered by severity.",
    [],
    { reasoning: "high", output: "A severity-ranked patch audit" }),
  recipe("review", "check-citations", "Check claims and citations", "Verify that claims are supported by the cited evidence.",
    "Review {{source}} and verify each material factual claim against its cited or available evidence. Flag unsupported, overstated, stale, or contradictory claims and recommend precise corrections.",
    [field("source", "Document or artifact", "What should Rasputin fact-check?", true)],
    { reasoning: "high", output: "A claim-by-claim evidence audit" }),
  recipe("review", "compare-versions", "Compare versions", "Explain meaningful changes and their consequences.",
    "Compare these versions: {{versions}}. Summarize substantive additions, removals, changed decisions, unresolved inconsistencies, and the practical impact. Ignore cosmetic differences unless they affect meaning.",
    [field("versions", "Versions or paths", "List the files or artifacts to compare.", true, true)],
    { reasoning: "medium", output: "A meaningful version comparison" }),
  recipe("review", "risk-review", "Identify risks", "Surface operational, security, delivery, and maintenance concerns.",
    "Perform a risk review of {{subject}}. Identify failure modes, likelihood, impact, warning signs, mitigations, ownership, and residual risk. Ground findings in available evidence and distinguish current problems from hypothetical risks.",
    [field("subject", "Subject", "A plan, system, change, document, or project.", true, true)],
    { reasoning: "high", output: "A prioritized risk register" }),
];

export function recipesForMode(mode) {
  return PROMPT_RECIPES.filter((item) => item.mode === mode);
}

export function featuredRecipes() {
  return PROMPT_RECIPES.filter((item) => item.featured);
}

export function initialRecipeValues(item) {
  return Object.fromEntries((item?.fields || []).map((itemField) => [itemField.id, ""]));
}

export function missingRecipeFields(item, values = {}) {
  return (item?.fields || []).filter((itemField) => itemField.required && !String(values[itemField.id] || "").trim());
}

export function buildRecipeObjective(item, values = {}) {
  if (!item) return "";
  const rendered = item.prompt.replace(/\{\{([a-zA-Z0-9_-]+)\}\}/g, (_, key) => String(values[key] || "").trim());
  return rendered
    .split("\n")
    .map((line) => line.replace(/\s+$/g, ""))
    .filter((line) => !/^[A-Za-z][^:]{0,60}:\s*$/.test(line.trim()))
    .filter((line, index, lines) => line.trim() || (index > 0 && lines[index - 1]?.trim()))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function modelSupportsAgenticRecipes(model) {
  if (!model) return false;
  return !model.managed || model.toolSupport === "agentic" || Boolean(model.toolCallParser);
}

export function recipeAvailability(item, { model, allowWebSearch = true } = {}) {
  if (!item) return { available: false, reason: "Recipe unavailable." };
  if (!model) return { available: false, reason: `No model is routed to ${item.mode} mode.` };
  if (item.requiresAgentic && !modelSupportsAgenticRecipes(model)) {
    return { available: false, reason: "The routed model is chat-only and cannot run this mode." };
  }
  if (item.requiresWeb && !allowWebSearch) {
    return { available: false, reason: "Web search is disabled in Security settings." };
  }
  return { available: true, reason: "" };
}
