(function () {
  "use strict";
  function setup() {
    const target = document.getElementById("placeholder-target");
    const choice = document.getElementById("placeholder-choice");
    const insert = document.getElementById("placeholder-insert");
    const description = document.getElementById("placeholder-description");
    const status = document.getElementById("placeholder-status");
    if (!target || !choice || !insert) return;
    function update() {
      const subject = target.value === "id_subject";
      Array.from(choice.options).forEach(option => { option.disabled = subject && option.dataset.multiline === "true"; });
      if (choice.selectedOptions[0]?.disabled) choice.value = Array.from(choice.options).find(option => !option.disabled)?.value || "";
      description.textContent = choice.selectedOptions[0]?.dataset.description || "";
      insert.disabled = !document.getElementById(target.value) || !choice.value;
    }
    ["id_subject", "id_body"].forEach(id => {
      document.getElementById(id)?.addEventListener("focus", () => { target.value = id; update(); });
    });
    target.addEventListener("change", update);
    choice.addEventListener("change", update);
    insert.addEventListener("click", () => {
      const field = document.getElementById(target.value);
      const option = choice.selectedOptions[0];
      if (!field || !option || option.disabled) return;
      const placeholder = "{" + option.value + "}";
      const start = field.selectionStart ?? field.value.length;
      const end = field.selectionEnd ?? field.value.length;
      field.focus();
      field.setRangeText(placeholder, start, end, "end");
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.setSelectionRange(start + placeholder.length, start + placeholder.length);
      status.textContent = "Inserted " + placeholder + " into " + (target.value === "id_body" ? "Body" : "Subject") + ". Save the template to keep this change.";
    });
    update();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup, { once: true });
  else setup();
}());
