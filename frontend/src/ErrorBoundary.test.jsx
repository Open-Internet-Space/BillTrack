import { act } from "react";
import { createRoot } from "react-dom/client";
import ErrorBoundary from "./ErrorBoundary";

test('a crashed screen offers an accessible reload warning without exposing the exception', () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const log = jest.spyOn(console, 'error').mockImplementation(() => {});
  const container = document.createElement('div');
  const root = createRoot(container);
  const Broken = () => { throw new Error('private-component-details'); };
  try {
    act(() => root.render(<ErrorBoundary><Broken /></ErrorBoundary>));
    expect(container.querySelector('[role="alert"]').textContent).toContain('Reloading discards unsaved input');
    expect(container.querySelector('button').textContent).toBe('Reload page');
    expect(container.textContent).not.toContain('private-component-details');
  } finally { act(() => root.unmount()); log.mockRestore(); }
});
