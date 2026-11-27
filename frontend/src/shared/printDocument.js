import API from '../api';

export async function openPrintDocument(path, showToast, label = 'invoice') {
  let popup;
  try { popup = window.open('about:blank', '_blank'); }
  catch { showToast?.(`Allow pop-ups to open the ${label}.`, false); return; }
  if (!popup) {
    showToast?.(`Allow pop-ups to open the ${label}.`, false);
    return;
  }
  popup.opener = null;
  let objectUrl;
  try {
    const document = await API.document(path);
    if (popup.closed) return;
    objectUrl = URL.createObjectURL(document);
    popup.addEventListener('load', () => URL.revokeObjectURL(objectUrl), { once: true });
    popup.location.replace(objectUrl);
  } catch (error) {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    popup.close();
    showToast?.(error.message || `${label[0].toUpperCase()}${label.slice(1)} could not be loaded.`, false);
  }
}
