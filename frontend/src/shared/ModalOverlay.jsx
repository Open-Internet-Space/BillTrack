import { useEffect, useRef } from "react";

export const ModalOverlay = ({ children, onClose, saving, error, sessionExpired, onSignIn, titleId = 'modal-title' }) => {
  const dialogRef = useRef(null);
  useEffect(() => {
    const trigger = document.activeElement;
    const dialog = dialogRef.current;
    dialog.showModal();
    return () => {
      dialog.close();
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  return <dialog ref={dialogRef} className="app-dialog" aria-labelledby={titleId} aria-busy={saving}
    onCancel={event => { event.preventDefault(); event.stopPropagation(); if (!saving) onClose(); }}>
    <fieldset disabled={saving} className="dialog-fields">{children}</fieldset>
    {saving && <p role="status" className="form-feedback">Saving… Please wait.</p>}
    {error && <p role="alert" className="form-feedback form-error">{error}</p>}
    {sessionExpired && <button type="button" data-sign-in className="btn-ghost" disabled={saving} onClick={onSignIn}>Sign in again</button>}
  </dialog>;
};
