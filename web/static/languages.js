// "Add translation" picker: a checkbox that enables a language list. The list
// shows each language by its own name; the value is the English name the
// server's translator expects. The first language is the default.

export function createLanguagePicker(container, languages) {
  const wrapper = document.createElement("div");
  wrapper.className = "language-picker";

  const label = document.createElement("label");
  label.className = "checkbox";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.id = "add-translation";
  label.append(checkbox, document.createTextNode(" Add translation"));

  const select = document.createElement("select");
  select.setAttribute("aria-label", "Translation language");
  select.disabled = true;
  for (const { name, label: ownName } of languages) {
    select.append(new Option(ownName, name));
  }

  checkbox.addEventListener("change", () => {
    select.disabled = !checkbox.checked;
  });
  wrapper.append(label, select);
  container.append(wrapper);

  return {
    // English name of the chosen language, or null without a translation.
    value: () => (checkbox.checked ? select.value : null),
    setDisabled: (disabled) => {
      checkbox.disabled = disabled;
      select.disabled = disabled || !checkbox.checked;
    },
  };
}
