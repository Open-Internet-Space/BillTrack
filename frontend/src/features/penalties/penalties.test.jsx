import { act, sampleBill, fillInput, choose, signedInApp } from "../../test-support/app";

test("penalty period and detail filters retain their correct total scope", async () => {
  const bills = [
    { ...sampleBill, id: 1, invoice_no: 'OCT', month: 10, year: 2026, days_overdue: 8, due_date: '2026-11-01' },
    { ...sampleBill, id: 2, invoice_no: 'NOV', month: 11, year: 2026, days_overdue: 4, due_date: '2026-11-02' },
    { ...sampleBill, id: 3, invoice_no: 'OLDER', month: 11, year: 2025, days_overdue: 50, due_date: '2025-11-01' },
  ];
  const { container, close } = await signedInApp(url => url.includes('/bills/')
    ? Promise.resolve({ ok: true, json: async () => bills }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Penalties').click());
    act(() => choose(container.querySelector('#penalty-year'), '2026'));
    act(() => choose(container.querySelector('#penalty-month'), '11'));
    expect(container.textContent).toContain('Total Penalty Due: ₹ 5.00');
    act(() => container.querySelector('button[aria-expanded]').click());
    expect(container.querySelector('tbody table tbody').textContent).toContain('NOV');
    act(() => fillInput(container.querySelector('#penalty-bills-from'), '2026-11-02'));
    act(() => fillInput(container.querySelector('#penalty-bills-to'), '2026-11-02'));
    expect(container.querySelector('tbody table tbody').children).toHaveLength(1);
    act(() => fillInput(container.querySelector('#penalty-bills-search'), 'missing'));
    expect(container.querySelector('tbody table tbody').children).toHaveLength(0);
    expect(container.textContent).toContain('Total Penalty Due: ₹ 5.00');
  } finally { close(); }
});

test("changing the parent penalty period resets the expanded bill page but keeps local filters", async () => {
  const bills = Array.from({ length: 24 }, (_, index) => ({ ...sampleBill, id: index + 1,
    invoice_no: `INV-${index + 1}`, month: index % 12 + 1, year: index < 12 ? 2025 : 2026, days_overdue: 10,
  }));
  const { container, close } = await signedInApp(url => url.includes('/bills/')
    ? Promise.resolve({ ok: true, json: async () => bills }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Penalties').click());
    act(() => container.querySelector('button[aria-expanded]').click());
    act(() => fillInput(container.querySelector('#penalty-bills-search'), 'INV'));
    const pager = container.querySelector('[aria-label="bills pagination"]');
    const next = () => [...pager.querySelectorAll('button')].find(button => button.textContent === 'Next');
    act(() => next().click());
    act(() => next().click());
    expect(pager.textContent).toContain('Showing 21-24 of 24 bills');
    act(() => choose(container.querySelector('#penalty-year'), '2026'));
    expect(pager.textContent).toContain('Showing 1-10 of 12 bills');
    expect(container.querySelector('#penalty-bills-search').value).toBe('INV');
  } finally { close(); }
});

test("expanded penalty bills paginate without changing the full penalty total", async () => {
  const bills = Array.from({ length: 12 }, (_, index) => ({ ...sampleBill,
    id: index + 1, invoice_no: `INV-${index + 1}`, days_overdue: 10,
    penalty_calculation: { formula: 'Example', result: '5', principal: '100', days: 10 },
  }));
  const { container, close } = await signedInApp(url => url.includes('/bills/')
    ? Promise.resolve({ ok: true, json: async () => bills }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Penalties').click());
    act(() => container.querySelector('button[aria-expanded]').click());
    expect(container.querySelector('tbody table tbody').children).toHaveLength(10);
    const pager = container.querySelector('[aria-label="bills pagination"]');
    act(() => [...pager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    expect(container.querySelector('tbody table tbody').children).toHaveLength(2);
    expect(container.textContent).toContain('INV-11');
    expect(container.textContent).toContain('Total Penalty Due: ₹ 60.00');
    act(() => [...container.querySelectorAll('button')].find(button => button.textContent === 'Calculation').click());
    expect(container.textContent).toContain('Example');
  } finally { close(); }
});
