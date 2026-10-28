# REAUnsloth home restoration

The 0.3.0 workstation build retained the hardware popup from the REAUnsloth work,
but omitted its later home redesign, commit `415c73831f0bccf212378fa2c9f8d153231362d4`
on `codex/unsloth-ui-polish`. Version 0.3.1 restores that home layout and incorporates
the subsequent request to remove the entire Chat header.

- Flat canvas, centered greeting and composer, compact sidebar, and response Options
  follow the recovered layout. The composer retains model selection and recipes.
- The Chat header markup and its status, branding, navigation, and settings controls
  are removed. Sidebar navigation/settings and the on-demand System status popup remain.
- Library opens saved content; Model Hub opens local models. More retains the other
  role-authorized tools. API, Training, and Scheduled remain directly accessible.
- Sidebar resizing persists existing widths; reset now returns to the reference's
  280px width. The separate `studio-home.css` import provides a visual rollback point.

Source verification: frontend build and desktop syntax passed; focused sidebar/shell
tests passed 11/11; desktop lifecycle/packaging tests passed 6/6 with process permissions;
documentation validation passed (45 Markdown files before this note). The first sandboxed
lifecycle attempt failed under restricted filesystem/process access and was stopped;
the permitted isolated run passed. The eight browser checks passed across the original
seven successful checks and the corrected welcome test. Its initial failure was an
overly strict class-order assertion, corrected to allow intervening CSS classes.

Rendered screenshots were inspected at 1440px and 390px. The welcome/Options check and
model picker also exercised 768px. Browser model data is deterministic fixture data,
not proof of real-model inference. Installer evidence is recorded separately after
installation; source verification alone does not establish the installed result.
