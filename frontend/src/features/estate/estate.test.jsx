import { act, fillInput, sampleBill, signedInApp } from '../../test-support/app';

const shops = [
  { id: 1, code: 'A-101', name: 'Snacks', location: 'Institute Canteen', category: 'day_food',
    active: true, space_type: 'space', occupancy_status: 'occupied', advertised_area: '150.0000' },
  { id: 2, code: 'N-401', name: 'Night utility', location: 'Hostel A', category: 'night_utility',
    active: true, space_type: 'space', occupancy_status: 'unknown' },
];
const terms = [{ id: 11, shop: 1, shop_code: 'A-101', tenant: 1, tenant_name: 'Test Allottee',
  award_reference: 'Award 2025/11', source_notice: '368/2025', start_date: '2025-07-01',
  end_date: '2026-06-30', effective_end: '2026-06-30', status: 'expired',
  possession_date: '2025-07-01', possession_reference: 'Possession memo', handover_date: null,
  actual_area: '150.0000', measurement_reference: 'Measurement memo', extension_number: 0 }];
const reply = data => Promise.resolve({ ok: true, json: async () => data });
const fixture = (url, options) => url.includes('/estate/attention/') ? reply([
  { kind: 'expired_unvacated', shop: 1, shop_code: 'A-101', allotment: 11,
    tenant_name: 'Test Allottee', end_date: '2026-06-30', as_of: '2026-11-13' }])
  : url.includes('/allotment-requirements/') ? reply([])
  : url.includes('/allotments/') ? reply(terms)
  : url.includes('/shops/') ? reply(options.method === 'POST' ? { id: 3 } : shops) : null;
const button = (container, label) => [...container.querySelectorAll('button')].find(node => node.textContent.trim() === label);

test('shops can be searched without confusing contractual expiry and physical occupancy', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    expect(button(container, 'Shops')).toBeDefined();
    await act(async () => button(container, 'Shops').click());
    expect(container.querySelector('h1').textContent).toBe('Shops');
    expect(container.textContent).toContain('A-101');
    expect(container.textContent).toContain('Occupied');
    expect(container.textContent).toContain('Availability unknown');
    await act(async () => fillInput(container.querySelector('#estate-search'), 'Hostel A'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody').textContent).toContain('N-401');
  } finally { close(); }
});

test('dashboard estate attention opens the specific allotment and its handover evidence', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    const entry = container.querySelector('[aria-label="Open allotment 11 for A-101"]');
    expect(entry).not.toBeNull();
    await act(async () => entry.click());
    expect(container.querySelector('h1').textContent).toBe('Allotments');
    const detail = container.querySelector('[aria-label="Allotment details"]');
    expect(detail).not.toBeNull();
    expect(detail.textContent).toContain('Award 2025/11');
    expect(detail.textContent).toContain('Not recorded');
    expect(detail.textContent).toContain('Possession memo');
  } finally { close(); }
});

test('allotment billing opens only that term and keeps its raise-bill context', async () => {
  const { container, close } = await signedInApp((url, options) => url.includes('/bills/') ? reply([
    { ...sampleBill, id: 21, allotment: 11, shop_code: 'A-101', invoice_no: 'SHOP-A', month: 6 },
    { ...sampleBill, id: 22, allotment: 12, shop_code: 'N-401', invoice_no: 'SHOP-N', month: 6 }]) : fixture(url, options));
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for A-101"]').click());
    await act(async () => button(container, 'View term bills').click());
    expect(container.querySelector('tbody').textContent).toContain('SHOP-A');
    expect(container.querySelector('tbody').textContent).not.toContain('SHOP-N');
    await act(async () => button(container, 'Show all allottee bills').click());
    expect(container.querySelector('tbody').textContent).toContain('SHOP-N');
  } finally { close(); }
});

test('accepted rent rates are recorded against the original award with approval evidence', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for A-101"]').click());
    await act(async () => button(container, 'Record accepted rate').click());
    act(() => {
      fillInput(container.querySelector('#rate-effective'), '2025-07-01');
      fillInput(container.querySelector('#rate-amount'), '12.0000');
      fillInput(container.querySelector('#rate-approval'), 'Reviewed accepted bid');
      fillInput(container.querySelector('#rate-reason'), 'Accepted rate as of original letter');
    });
    await act(async () => container.querySelector('form[aria-label="Reviewed rent rate"]').dispatchEvent(new Event('submit', {bubbles:true,cancelable:true})));
    const save = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/rent-revisions/') && options?.method === 'POST');
    expect(JSON.parse(save[1].body)).toMatchObject({original_award:11, effective_date:'2025-07-01',
      rate:'12.0000', approval_reference:'Reviewed accepted bid'});
  } finally { close(); }
});

test('raising a historical term never silently selects another current shop', async () => {
  const {container,close}=await signedInApp((url,options)=>url.includes('/allotments/') ? reply([...terms,
    {...terms[0],id:12,shop:2,shop_code:'N-401',start_date:'2020-01-01',end_date:'2100-12-31',effective_end:'2100-12-31',status:'current'}]) : fixture(url,options));
  try {
    await act(async()=>container.querySelector('[aria-label="Open allotment 11 for A-101"]').click());
    await act(async()=>button(container,'Raise bill for term').click());
    expect(container.querySelector('#billform-allotment').value).toBe('');
    act(()=>{fillInput(container.querySelector('#billform-from-month'),'2026-06');fillInput(container.querySelector('#billform-to-month'),'2026-06');});
    expect(container.querySelector('#billform-allotment').value).toBe('11');
  } finally {close();}
});

test('add shop uses the existing modal save flow and sends explicit identity fields', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    expect(button(container, 'Shops')).toBeDefined();
    await act(async () => button(container, 'Shops').click());
    await act(async () => button(container, 'Add shop').click());
    await act(async () => {
      fillInput(container.querySelector('#shop-code'), 'B-305');
      fillInput(container.querySelector('#shop-name'), 'Laundry');
    });
    const form = container.querySelector('form[aria-label="Shop details"]');
    await act(async () => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    const request = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/shops/') && options.method === 'POST');
    expect(request).toBeDefined();
    expect(JSON.parse(request[1].body)).toMatchObject({ code: 'B-305', name: 'Laundry', category: 'utility' });
    expect(container.querySelector('dialog')).toBeNull();
  } finally { close(); }
});

test('allottee shop history scopes the list and can return to all allotments', async () => {
  const { container, close } = await signedInApp((url, options) => url.includes('/allotments/')
    ? reply([...terms, { ...terms[0], id: 12, shop: 2, shop_code: 'N-401', tenant: 2, tenant_name: 'Other allottee' }])
    : fixture(url, options));
  try {
    await act(async () => button(container, 'Allottees').click());
    await act(async () => button(container, 'Shop history').click());
    expect(container.querySelector('tbody').textContent).toContain('A-101');
    expect(container.querySelector('tbody').textContent).not.toContain('N-401');
    await act(async () => button(container, 'Show all allotments').click());
    expect(container.querySelector('tbody').textContent).toContain('N-401');
  } finally { close(); }
});

test('renewal starts a fresh term without copying prior possession and approval evidence', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for A-101"]').click());
    await act(async () => button(container, 'Record renewal').click());
    expect(container.querySelector('#term-start_date').value).toBe('2026-07-01');
    expect(container.querySelector('#term-end_date').value).toBe('2027-06-30');
    expect(container.querySelector('#term-shop').disabled).toBe(true);
    expect(container.querySelector('#term-tenant').disabled).toBe(true);
    expect(container.querySelector('#term-possession_date').value).toBe('');
    expect(container.querySelector('#term-approval_reference').value).toBe('');
    expect(container.querySelector('#term-award_reference').value).toBe('');
  } finally { close(); }
});

test('a rejected save keeps the shop inputs for correction', async () => {
  const { container, close } = await signedInApp((url, options) => url.endsWith('/shops/') && options.method === 'POST'
    ? Promise.resolve({ ok: false, status: 400, json: async () => ({ code: ['Already recorded'] }) }) : fixture(url, options));
  try {
    await act(async () => button(container, 'Shops').click());
    await act(async () => button(container, 'Add shop').click());
    await act(async () => { fillInput(container.querySelector('#shop-code'), 'A-101'); fillInput(container.querySelector('#shop-name'), 'Keep this name'); });
    await act(async () => container.querySelector('form[aria-label="Shop details"]').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(container.querySelector('#shop-name').value).toBe('Keep this name');
    expect(container.querySelector('dialog [role="alert"]').textContent).toContain('Already recorded');
  } finally { close(); }
});
