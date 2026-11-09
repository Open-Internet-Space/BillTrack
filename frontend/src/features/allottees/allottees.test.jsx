import { act, sampleTenant, sampleBill, fillInput, choose, signedInApp } from "../../test-support/app";

test('Allottees displays the last billed month and never-billed state', async () => {
  const { container, close } = await signedInApp(url => url.includes('/tenants/')
    ? Promise.resolve({ ok: true, json: async () => [
      { ...sampleTenant, last_billed_month: 'January 2026' },
      { ...sampleTenant, id: 2, name: 'Unbilled allottee', last_billed_month: 'Never billed' },
    ] }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent === 'Allottees').click());
    expect(container.querySelector('h1').textContent).toBe('Allottees');
    expect(container.querySelector('thead').textContent).toContain('LAST BILLED MONTH');
    expect(container.querySelector('tbody').textContent).toContain('January 2026');
    expect(container.querySelector('tbody').textContent).toContain('Never billed');
  } finally { close(); }
});

test('refresh preserves tenant filters and shows a retry when loading fails', async () => {
  let fail = false;
  const { container, close } = await signedInApp(url => fail && url.includes('/tenants/')
    ? Promise.resolve({ ok: false, json: async () => ({ detail: 'Refresh unavailable' }) }) : null);
  const button = label => [...container.querySelectorAll('button')].find(node => node.textContent === label);
  try {
    await act(async () => button('Allottees').click());
    act(() => fillInput(container.querySelector('#tenants-search'), 'Test'));
    fail = true;
    await act(async () => button('↻ Refresh').click());
    expect(container.querySelector('[role="alert"]').textContent).toContain('Refresh unavailable');
    fail = false;
    await act(async () => button('Retry').click());
    expect(container.querySelector('#tenants-search').value).toBe('Test');
  } finally { close(); }
});

test("tenant filters combine search, type and activity and reset pagination", async () => {
  const tenants = Array.from({ length: 22 }, (_, index) => ({ ...sampleTenant,
    id: index + 1, name: `Allottee ${index + 1}`, type: index === 21 ? 'Canteen' : 'Shop',
    active: index !== 21, email: index === 21 ? 'special@example.com' : '',
  }));
  const { container, close } = await signedInApp(url => url.includes('/tenants/')
    ? Promise.resolve({ ok: true, json: async () => tenants }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Allottees').click());
    const pager = container.querySelector('[aria-label="allottees pagination"]');
    act(() => [...pager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    act(() => fillInput(container.querySelector('#tenants-search'), ' SPECIAL@example.com '));
    expect(pager.textContent).toContain('Showing 1-1 of 1 allottees');
    act(() => choose(container.querySelector('#tenants-type'), 'Canteen'));
    act(() => choose(container.querySelector('#tenants-active'), 'inactive'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    act(() => [...container.querySelector('[aria-label="Allottee filters"]').querySelectorAll('button')].find(button => button.textContent === 'Reset').click());
    expect(pager.textContent).toContain('Showing 1-10 of 22 allottees');
  } finally { close(); }
});

test("bill search and tenant type combine with receipt filters", async () => {
  const bills = [{ ...sampleBill, tenant_type: 'Shop', dispatch_ref_no: 'DIS-ALPHA' },
    { ...sampleBill, id: 2, invoice_no: 'OTHER', tenant_type: 'Canteen', issue_date: null }];
  const { container, close } = await signedInApp(url => url.includes('/bills/')
    ? Promise.resolve({ ok: true, json: async () => bills }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Bills').click());
    act(() => fillInput(container.querySelector('#bills-search'), 'dis-alpha'));
    act(() => choose(container.querySelector('#bills-type'), 'Shop'));
    act(() => choose(container.querySelector('#bills-receipt'), 'confirmed'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody').textContent).toContain('TEST-1');
    act(() => choose(container.querySelector('#bills-receipt'), 'pending'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(0);
  } finally { close(); }
});

test("tenants paginate with the Bills row choices", async () => {
  const tenants = Array.from({ length: 32 }, (_, index) => ({ ...sampleTenant, id: index + 1, name: `Allottee ${index + 1}` }));
  const { container, close } = await signedInApp(url => url.includes('/tenants/')
    ? Promise.resolve({ ok: true, json: async () => tenants }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Allottees').click());
    expect(container.querySelectorAll('tbody tr')).toHaveLength(10);
    const pager = container.querySelector('[aria-label="allottees pagination"]');
    expect(pager.textContent).toContain('Showing 1-10 of 32 allottees');
    const rows = pager.querySelector('select');
    expect([...rows.options].map(option => option.value)).toEqual(['10', '15', '20', '25', '30']);
    act(() => { rows.value = '15'; rows.dispatchEvent(new Event('change', { bubbles: true })); });
    act(() => [...pager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    expect(container.querySelectorAll('tbody tr')).toHaveLength(15);
    expect(pager.textContent).toContain('Showing 16-30 of 32 allottees');
  } finally { close(); }
});

test("dashboard lists paginate all overdue allottees and upcoming bills", async () => {
  const bills = Array.from({ length: 24 }, (_, index) => ({ ...sampleBill, id: index + 1,
    tenant: index + 1, tenant_name: `Overdue ${index + 1}`, days_overdue: index + 1,
    due_date: '2026-01-01' })).concat(Array.from({ length: 12 }, (_, index) => ({
      ...sampleBill, id: index + 25, tenant: index + 25, tenant_name: `Upcoming ${index + 1}`,
    })));
  const { container, close } = await signedInApp(url => url.includes('/bills/')
    ? Promise.resolve({ ok: true, json: async () => bills }) : null);
  try {
    const overdue = container.querySelector('[aria-label="Most overdue allottees"]');
    const upcoming = container.querySelector('[aria-label="Upcoming due dates"]');
    expect(overdue.querySelectorAll('.dashboard-entry')).toHaveLength(10);
    expect(upcoming.querySelectorAll('.dashboard-entry')).toHaveLength(10);
    const pager = container.querySelector('[aria-label="overdue allottees pagination"]');
    act(() => [...pager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    act(() => [...pager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    expect(overdue.querySelectorAll('.dashboard-entry')).toHaveLength(4);
    expect(upcoming.querySelectorAll('.dashboard-entry')).toHaveLength(10);
  } finally { close(); }
});

test('allottees sort last billed periods across pages and reset sorting', async () => {
  const allottees = Array.from({ length: 11 }, (_, index) => ({ ...sampleTenant,
    id: index + 1, name: `Allottee ${String(index + 1).padStart(2, '0')}`, last_billed_month: 'December 2025' }));
  allottees.push({ ...sampleTenant, id: 99, name: 'Z newest', last_billed_month: 'January 2026' },
    { ...sampleTenant, id: 100, name: 'Never billed allottee', last_billed_month: 'Never billed' });
  const { container, close } = await signedInApp(url => url.includes('/tenants/')
    ? Promise.resolve({ ok: true, json: async () => url.includes('page=2')
      ? { results: allottees.slice(11), next: null }
      : { results: allottees.slice(0, 11), next: '/api/tenants/?page=2' } }) : null);
  const firstName = () => container.querySelector('tbody tr td').textContent;
  try {
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent === 'Allottees').click());
    const sort = container.querySelector('#tenants-sort');
    expect(sort).not.toBeNull();
    act(() => choose(sort, 'billed_desc'));
    expect(firstName()).toBe('Z newest');
    const pager = container.querySelector('[aria-label="allottees pagination"]');
    act(() => [...pager.querySelectorAll('button')].find(node => node.textContent === 'Next').click());
    expect(container.querySelector('tbody').textContent).toContain('Never billed allottee');
    act(() => choose(sort, 'billed_asc'));
    expect(firstName()).toBe('Never billed allottee');
    expect(pager.textContent).toContain('Showing 1-10');
    expect(container.querySelectorAll('tbody tr')[1].querySelector('td').textContent).toBe('Allottee 01');
    act(() => [...container.querySelector('[aria-label="Allottee filters"]').querySelectorAll('button')].find(node => node.textContent === 'Reset').click());
    expect(sort.value).toBe('name');
    expect(firstName()).toBe('Allottee 01');
  } finally { close(); }
});

test('allottee Raise Bill opens its bills and preselects it in the existing bill form', async () => {
  const { container, close } = await signedInApp(url => url.includes('/tenants/')
    ? Promise.resolve({ ok: true, json: async () => [sampleTenant,
      { ...sampleTenant, id: 2, name: 'Other Allottee' },
      { ...sampleTenant, id: 3, name: 'Inactive Allottee', active: false }] }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent === 'Allottees').click());
    expect(container.querySelector('[aria-label="Raise bill for Other Allottee"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Raise bill for Inactive Allottee"]').disabled).toBe(true);
    await act(async () => container.querySelector('[aria-label="Raise bill for Other Allottee"]').click());
    expect(container.querySelector('h1').textContent).toBe('Bills');
    expect(container.querySelector('#bills-tenant').value).toBe('2');
    expect(container.querySelector('dialog')).toBeNull();
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent === '+ Raise Bill').click());
    expect(container.querySelector('#billform-tenant').value).toBe('2');
    expect(global.fetch.mock.calls.some(([url, options]) => url.includes('/bills/') && options?.method === 'POST')).toBe(false);
  } finally { close(); }
});
