document.addEventListener('DOMContentLoaded', () => {
  ['contact', 'email', 'gstin', 'address'].forEach(field => {
    const input = document.getElementById(`id_${field}`);
    const checkbox = document.getElementById(`id_${field}_not_provided`);
    if (!input || !checkbox) return;

    const sync = () => {
      input.disabled = checkbox.checked;
      if (checkbox.checked) input.value = '';
    };
    checkbox.addEventListener('change', sync);
    sync();
  });
});
