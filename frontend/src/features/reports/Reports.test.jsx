import { act } from 'react';
import { createRoot } from 'react-dom/client';
import Reports from './Reports';

global.IS_REACT_ACT_ENVIRONMENT = true;

test('downloads require a successful preview and are invalidated by filter changes', async () => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  const api = { get: jest.fn(async () => ({ title: 'Pending bills', count: 11,
    columns: [{ key: 'vendor', label: 'Vendor' }, { key: 'balance', label: 'Principal due', numeric: true }],
    rows: Array.from({ length: 11 }, (_, index) => ({ vendor: `Vendor ${index}`, balance: '70.00' })),
    totals: { balance: '770.00' }, snapshot: 'reviewed-snapshot', notes: [], filters: 'Through 31 January 2026', generated_at: '2026-01-31 12:00 IST' })),
    download: jest.fn(async () => {}) };
  const button = label => [...container.querySelectorAll('button')].find(node => node.textContent === label);
  try {
    act(() => root.render(<Reports api={api} tenants={[]} />));
    expect(button('Download XLSX').disabled).toBe(true);
    await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(10);
    expect(container.textContent).toContain('770.00');
    await act(async () => button('Download XLSX').click());
    expect(api.download).toHaveBeenCalledWith('/reports/', { snapshot: 'reviewed-snapshot', output: 'xlsx', columns: ['vendor', 'balance'] }, expect.stringContaining('.xlsx'));
    expect([...container.querySelectorAll('input[type="checkbox"]')].every(input => input.checked)).toBe(true);
    act(() => container.querySelector('input[value="vendor"]').click());
    expect(container.querySelector('table').textContent).not.toContain('Vendor 0');
    expect(container.querySelector('tfoot').textContent).toContain('770.00');
    await act(async () => button('Download PDF').click());
    expect(api.download).toHaveBeenLastCalledWith('/reports/', { snapshot: 'reviewed-snapshot', output: 'pdf', columns: ['balance'] }, expect.stringContaining('.pdf'));
    const callsBeforeRefresh = api.get.mock.calls.length;
    await act(async () => button('↻ Refresh').click());
    expect(api.get).toHaveBeenCalledTimes(callsBeforeRefresh + 1);
    expect(container.querySelector('input[value="vendor"]').checked).toBe(false);
    expect(container.querySelector('input[value="balance"]').checked).toBe(true);
    act(() => container.querySelector('input[value="balance"]').click());
    expect(button('Download DOCX').disabled).toBe(true);
    expect(container.textContent).toContain('Select at least one column');
    await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect([...container.querySelectorAll('input[type="checkbox"]')].every(input => input.checked)).toBe(true);
    act(() => {
      const select = container.querySelector('#report-kind');
      select.value = 'payments';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    expect(button('Download DOCX').disabled).toBe(true);
    expect(container.querySelector('table')).toBeNull();
  } finally { act(() => root.unmount()); container.remove(); }
});

test('failed previews show an error and keep downloads disabled', async () => {
  const container = document.createElement('div');
  const root = createRoot(container);
  const api = { get: jest.fn(async () => { throw new Error('Report could not load'); }) };
  try {
    act(() => root.render(<Reports api={api} tenants={[]} />));
    await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(container.querySelector('[role="alert"]').textContent).toContain('Report could not load');
    expect([...container.querySelectorAll('button')].find(node => node.textContent === 'Download PDF').disabled).toBe(true);
  } finally { act(() => root.unmount()); }
});
