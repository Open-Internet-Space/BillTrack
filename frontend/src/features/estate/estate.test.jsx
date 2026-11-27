import { act, fillInput, choose, sampleBill, signedInApp } from '../../test-support/app';

const terms = [{ id: 11, shop: 1, shop_code: 'A-101', tenant: 1, tenant_name: 'Test Allottee',
  award_reference: 'Award 2025/11', source_notice: '368/2025', start_date: '2025-07-01',
  end_date: '2026-06-30', effective_end: '2026-06-30', status: 'expired',
  possession_date: '2025-07-01', possession_reference: 'Possession memo', handover_date: null,
  actual_area: '150.0000', measurement_reference: 'Measurement memo', extension_number: 0 }];
const reply = data => Promise.resolve({ ok: true, json: async () => data });
const fixture = url => url.includes('/auth/me/') ? reply({ username: 'tester', allotment_details_enabled: true })
  : url.includes('/auth/login/') ? reply({ token: 'test-token', user: { username: 'tester', allotment_details_enabled: true } })
  : url.includes('/estate/attention/') ? reply([
  { kind: 'expired_unvacated', shop: 1, shop_code: 'A-101', allotment: 11,
    tenant_name: 'Test Allottee', end_date: '2026-06-30', as_of: '2026-11-13' }])
  : url.includes('/allotment-requirements/') ? reply([])
  : url.includes('/allotments/') ? reply(terms)
  : null;
const button = (container, label) => [...container.querySelectorAll('button')].find(node => node.textContent.trim() === label);

test('dashboard estate attention opens the specific allotment and its handover evidence', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    const entry = container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]');
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

test('deleting from term history previews and removes only the selected term', async () => {
  const preview = jest.spyOn(window, 'confirm').mockReturnValue(true);
  const reason = jest.spyOn(window, 'prompt').mockReturnValue('Term entered in error');
  const other = { ...terms[0], id: 12, award_reference: 'Retained term' };
  let removed = false;
  const { container, close } = await signedInApp((url, options) => {
    if (url.endsWith('/allotments/11/deletion-preview/')) return reply({ affected: ['Delete: allotment #11'], confirmation: 'reviewed' });
    if (url.endsWith('/allotments/11/') && options.method === 'DELETE') {
      removed = true;
      return Promise.resolve({ ok: true, status: 204 });
    }
    if (url.endsWith('/allotments/')) return reply(removed ? [other] : [...terms, other]);
    return fixture(url);
  });
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, 'View term history').click());
    const list = container.querySelector('[aria-label="Estate records"]');
    await act(async () => list.querySelector('[aria-label="Delete term Award 2025/11"]').click());
    expect(preview).toHaveBeenCalledWith(expect.stringContaining('Delete: allotment #11'));
    const [, options] = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/allotments/11/') && options.method === 'DELETE');
    expect(JSON.parse(options.body)).toEqual({ change_reason: 'Term entered in error', confirmation: 'reviewed' });
    const currentList = container.querySelector('[aria-label="Estate records"]');
    expect(currentList.textContent).toContain('Retained term');
    expect(currentList.textContent).not.toContain('Award 2025/11');
  } finally { close(); preview.mockRestore(); reason.mockRestore(); }
});

test('an existing renewal can record deposit carry-forward with additional details off', async () => {
  const renewal = { ...terms[0], renewal_of: 10, original_award_id: 10, extension_number: 1,
    letter_issued_on: '2025-06-01', performance_reference: 'Performance review', approval_reference: 'Renewal approval',
    carry_forward_deposit: false };
  const { container, close } = await signedInApp((url, options) => {
    if (url.includes('/auth/me/') || url.includes('/auth/login/')) {
      const user = { username: 'tester', allotment_details_enabled: false };
      return reply({ ...user, token: 'test-token', user });
    }
    if (url.endsWith('/allotments/11/') && options?.method === 'PATCH') return reply(renewal);
    if (url.includes('/allotments/')) return reply([renewal]);
    return fixture(url);
  });
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]').click());
    const detail = container.querySelector('[aria-label="Allotment details"]');
    expect(detail.textContent).not.toContain('Physical handover');
    await act(async () => button(detail, 'Edit term').click());
    const dialog = container.querySelector('dialog');
    const choice = [...dialog.querySelectorAll('label')].find(label => label.textContent.includes('Carry forward existing security deposit'));
    await act(async () => choice.querySelector('input').click());
    await act(async () => {
      fillInput(dialog.querySelector('#term-change_reason'), 'Allottee requested carry-forward');
      button(dialog, 'Save allotment').click();
    });
    const save = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/allotments/11/') && options?.method === 'PATCH');
    expect(JSON.parse(save[1].body).carry_forward_deposit).toBe(true);
  } finally { close(); }
});

test('a superuser can link a separately recorded extension and select its existing fee', async () => {
  const later = { ...terms[0], id: 12, award_reference: 'Second-year letter', start_date: '2026-07-01', end_date: '2027-06-30' };
  const user = { username: 'estate-admin', is_superuser: true };
  const { container, close } = await signedInApp(url => {
    if (url.includes('/auth/me/')) return reply(user);
    if (url.includes('/auth/login/')) return reply({ token: 'test-token', user });
    if (url.endsWith('/link-extension/')) return reply({ ...later, renewal_of: 11 });
    if (url.endsWith('/allotments/')) return reply([...terms, later]);
    if (url.includes('?kind=extension_fee&')) return reply([{ allotment: 12, description: 'Extension for second year', balance_due: '1180.00' }]);
    return fixture(url);
  });
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, 'View term history').click());
    await act(async () => button(container, 'Link as extension').click());
    const form = container.querySelector('[aria-label="Link existing extension"]');
    act(() => {
      choose(form.querySelector('#extension-preceding-term'), '11');
      fillInput(form.querySelector('#extension-approval'), 'Approved extension');
      fillInput(form.querySelector('#extension-performance'), 'Performance minutes');
      fillInput(form.querySelector('#extension-reason'), 'Correct the original-award classification');
    });
    act(() => form.querySelector('input[type="checkbox"]').click());
    await act(async () => button(form, 'Link as extension').click());
    const [, options] = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/allotments/12/link-extension/') && options.method === 'POST');
    expect(JSON.parse(options.body)).toMatchObject({ previous_id: '11', move_fee: true, approval: 'Approved extension', performance: 'Performance minutes' });
  } finally { close(); }
});

test('allotment billing opens only that term and keeps its raise-bill context', async () => {
  const { container, close } = await signedInApp((url, options) => url.includes('/bills/') ? reply([
    { ...sampleBill, id: 21, allotment: 11, shop_code: 'A-101', invoice_no: 'SHOP-A', month: 6 },
    { ...sampleBill, id: 22, allotment: 12, shop_code: 'N-401', invoice_no: 'SHOP-N', month: 6 }]) : fixture(url, options));
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]').click());
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
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]').click());
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

test('the allottee profile adds successive rates by month and date', async () => {
  const rates = [];
  const { container, close } = await signedInApp((url, options) => {
    if (url === '/api/rent-revisions/' && options.method === 'POST') {
      const row = { ...JSON.parse(options.body), id: rates.length + 1 };
      rates.push(row);
      return reply(row);
    }
    if (url.includes('/rent-revisions/?original_award__tenant=1')) return reply([...rates]);
    return fixture(url);
  });
  const field = id => container.querySelector(`#${id}`);
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, 'Edit').click());
    await act(async () => button(container.querySelector('dialog'), 'Rent rates').click());
    expect(container.querySelector('h1').textContent).toBe('Rent rates');
    await act(async () => button(container, 'Record accepted rate').click());
    act(() => choose(field('rate-effective-mode'), 'month'));
    act(() => fillInput(field('rate-effective'), '2026-03'));
    act(() => fillInput(field('rate-amount'), '10'));
    await act(async () => button(container, 'Save rent rate').click());
    await act(async () => button(container, 'Add rent revision').click());
    act(() => fillInput(field('rate-effective'), '2026-05-20'));
    act(() => fillInput(field('rate-amount'), '15'));
    await act(async () => button(container, 'Save rent rate').click());
    expect(rates.map(({ original_award, effective_date, rate }) => [original_award, effective_date, rate]))
      .toEqual([[11, '2026-03-01', '10'], [11, '2026-05-20', '15']]);
    expect(container.querySelectorAll('[aria-label="Rent schedule"] li')).toHaveLength(2);
  } finally { close(); }
});

test('raising a historical term never silently selects another current shop', async () => {
  const {container,close}=await signedInApp((url,options)=>url.includes('/allotments/') ? reply([...terms,
    {...terms[0],id:12,shop:2,shop_code:'N-401',start_date:'2020-01-01',end_date:'2100-12-31',effective_end:'2100-12-31',status:'current'}]) : fixture(url,options));
  try {
    await act(async()=>container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]').click());
    await act(async()=>button(container,'Raise bill for term').click());
    expect(container.querySelector('#billform-allotment').value).toBe('');
    act(()=>{fillInput(container.querySelector('#billform-from-month'),'2026-06');fillInput(container.querySelector('#billform-to-month'),'2026-06');});
    expect(container.querySelector('#billform-allotment').value).toBe('11');
  } finally {close();}
});

test('term history scopes the list and preserves the register search on return', async () => {
  const { container, close } = await signedInApp((url, options) => url.includes('/allotments/')
    ? reply([...terms, { ...terms[0], id: 12, shop: 2, shop_code: 'N-401', tenant: 2, tenant_name: 'Other allottee' }])
    : fixture(url, options));
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => fillInput(container.querySelector('#tenants-search'), 'Test Allottee'));
    await act(async () => button(container, 'View term history').click());
    const table = container.querySelector('[aria-label="Estate records"] tbody');
    expect(table.textContent).toContain('Test Allottee');
    expect(table.textContent).not.toContain('Other allottee');
    await act(async () => button(container, 'Details').click());
    expect(table.textContent).not.toContain('Other allottee');
    await act(async () => button(container, 'Record term').click());
    expect(container.querySelector('#term-tenant').value).toBe('1');
    expect(container.querySelector('#term-shop')).toBeNull();
    expect(button(container, 'Find premises')).toBeUndefined();
    expect(global.fetch.mock.calls.some(([url]) => url.includes('/shops/'))).toBe(false);
    await act(async () => button(container, 'Cancel').click());
    await act(async () => button(container, 'Back to allotments').click());
    expect(container.querySelector('#tenants-search').value).toBe('Test Allottee');
  } finally { close(); }
});

test('renewal starts a fresh term without copying prior possession and approval evidence', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]').click());
    await act(async () => button(container, 'Record renewal').click());
    expect(container.querySelector('#term-start_date').value).toBe('2026-07-01');
    expect(container.querySelector('#term-end_date').value).toBe('2027-06-30');
    expect(container.querySelector('#term-shop')).toBeNull();
    expect(container.querySelector('#term-tenant').disabled).toBe(true);
    expect(container.querySelector('#term-possession_date').value).toBe('');
    expect(container.querySelector('#term-approval_reference').value).toBe('');
    expect(container.querySelector('#term-award_reference').value).toBe('');
  } finally { close(); }
});

test('renewal opens a date exception prompt with additional details off and preserves the form on cancel', async () => {
  const { container, close } = await signedInApp(url => url.includes('/auth/') ? null : fixture(url));
  const input = id => container.querySelector(`#${id}`);
  const writes = () => global.fetch.mock.calls.filter(([url, options]) => url.endsWith('/allotments/') && options.method === 'POST');
  try {
    await act(async () => container.querySelector('[aria-label="Open allotment 11 for Test Allottee"]').click());
    await act(async () => button(container, 'Record renewal').click());
    const form = container.querySelector('[aria-label="Allotment form"]');
    act(() => {
      fillInput(input('term-award_reference'), 'Extension order');
      fillInput(input('term-letter_issued_on'), '2026-07-15');
      fillInput(input('term-end_date'), '2027-07-31');
      fillInput(input('term-performance_reference'), 'Review record');
      fillInput(input('term-approval_reference'), 'Renewal order');
    });
    expect(input('term-exception_reference')).toBeNull();
    await act(async () => button(form, 'Record renewal').click());
    const dialog = () => container.querySelector('dialog[aria-labelledby="date-exception-title"]');
    expect(dialog().textContent).toContain('The term starts before the allotment letter was issued');
    expect(dialog().textContent).toContain('The renewal exceeds one year');
    expect(writes()).toHaveLength(0);
    act(() => dialog().dispatchEvent(new Event('cancel', { bubbles: true, cancelable: true })));
    expect(dialog()).toBeNull();
    expect(input('term-award_reference').value).toBe('Extension order');
    await act(async () => button(form, 'Record renewal').click());
    act(() => {
      fillInput(input('date-exception-approval'), 'Exception approval No. 7');
      fillInput(input('date-exception-reason'), 'Approved continued operation during renewal review');
    });
    await act(async () => button(dialog(), 'Save with exception').click());
    expect(JSON.parse(writes()[0][1].body)).toMatchObject({ award_reference: 'Extension order', renewal_of: 11,
      exception_reference: 'Exception approval No. 7', exception_reason: 'Approved continued operation during renewal review' });
  } finally { close(); }
});

test('recording an allotment keeps each date with its own reference in both rent modes', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, 'View term history').click());
    await act(async () => button(container, 'Record term').click());
    const form = container.querySelector('form[aria-label="Allotment form"]');
    const field = id => form.querySelector(`#term-${id}`);
    const checkPair = (date, reference) => {
      const pair = field(date).closest('.estate-form-pair');
      expect([...pair.querySelectorAll('input')].map(node => node.id)).toEqual([`term-${date}`, `term-${reference}`]);
      expect(field(date).type).toBe('date');
      expect(field(reference).type).toBe('text');
      expect(field(reference).labels[0].control).toBe(field(reference));
    };
    for (const basis of ['area', 'flat']) {
      act(() => choose(field('rent-basis'), basis));
      checkPair('letter_issued_on', 'award_reference');
      checkPair('rate-as-of', 'approved_rate_reference');
      checkPair('possession_date', 'possession_reference');
      checkPair('termination_date', 'termination_reference');
      checkPair('handover_date', 'handover_reference');
      checkPair('vacation_deadline', 'vacation_reference');
    }
    expect(field('exception_reference').closest('.estate-form-pair')).toBeNull();
  } finally { close(); }
});


test('enabled premises can be managed and optionally selected on a term', async () => {
  const user = { username: 'tester', premises_enabled: true };
  const { container, close } = await signedInApp(url => {
    if (url.endsWith('/auth/me/')) return reply(user);
    if (url.endsWith('/auth/login/')) return reply({ token: 'test-token', user });
    if (url.endsWith('/shops/')) return reply([{ id: 1, code: 'A-101', name: 'Office', active: true, occupancy_status: 'vacant' }]);
    return fixture(url);
  });
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, 'Find premises').click());
    expect(container.querySelector('[aria-label="Premises records"]').textContent).toContain('Vacant');
    await act(async () => button(container, 'Add premises').click());
    expect(container.querySelector('form[aria-label="Premises details"]')).not.toBeNull();
    await act(async () => button(container, 'Cancel').click());
    await act(async () => button(container, 'Back to allotments').click());
    await act(async () => button(container, 'View term history').click());
    await act(async () => button(container, 'Record term').click());
    const select = container.querySelector('#term-shop');
    expect(select.required).toBe(false);
    expect(select.value).toBe('');
    act(() => choose(select, '1'));
    expect(select.value).toBe('1');
  } finally { close(); }
});


test('a new term starts with blank source notice and supports a flat charge without area', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, 'View term history').click());
    await act(async () => button(container, 'Record term').click());
    expect(container.querySelector('#term-source_notice').value).toBe('');
    expect(container.querySelector('#term-accepted-rate').labels[0].textContent).toContain('per sq ft');
    act(() => choose(container.querySelector('#term-rent-basis'), 'flat'));
    expect(container.querySelector('#term-actual_area')).toBeNull();
    expect(container.querySelector('#term-measurement_reference')).toBeNull();
    expect(container.querySelector('#term-accepted-rate').labels[0].textContent).toContain('Flat monthly charge');
  } finally { close(); }
});


test('add allotment submits optional contract and register fields in one request', async () => {
  const { container, close } = await signedInApp(url => url.includes('/auth/') ? null : fixture(url));
  const input = id => container.querySelector(`#${id}`);
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, '+ Add Allotment').click());
    expect(input('term-award_reference')).toBeNull();
    act(() => container.querySelector('[aria-label="Contract details"] input[type="checkbox"]').click());
    act(() => choose(input('term-rent-basis'), 'flat'));
    act(() => {
      fillInput(input('tenantform-name'), 'Example office');
      fillInput(input('tenantform-type'), 'Office');
      fillInput(input('term-award_reference'), 'Office award');
      fillInput(input('term-letter_issued_on'), '2026-11-01');
      fillInput(input('term-start_date'), '2026-11-01');
      fillInput(input('term-end_date'), '2027-10-31');
      fillInput(input('term-accepted-rate'), '1500.00');
    });
    expect(input('term-source_notice')).toBeNull();
    expect(input('term-approved_rate_reference')).toBeNull();
    expect(input('term-rate-as-of')).toBeNull();
    expect(input('term-possession_date')).toBeNull();
    await act(async () => button(container, 'Add Allotment').click());
    const [, call] = global.fetch.mock.calls.find(([url, options]) => url === '/api/tenants/' && options.method === 'POST');
    const payload = JSON.parse(call.body);
    expect(payload).toMatchObject({
      name: 'Example office', type: 'Office',
      contract: { award_reference: 'Office award', rent_basis: 'flat', actual_area: null, accepted_rate_amount: '1500.00' },
    });
    expect(payload.contract).not.toHaveProperty('approved_rate_reference');
    expect(payload.contract).not.toHaveProperty('possession_date');
    expect(global.fetch.mock.calls.some(([url, options]) => url.startsWith('/api/allotments/') && options.method === 'POST')).toBe(false);
  } finally { close(); }
});


test('an allotment can save every essential contract field as Not Available', async () => {
  const { container, close } = await signedInApp(fixture);
  try {
    await act(async () => button(container, 'Allotments').click());
    await act(async () => button(container, '+ Add Allotment').click());
    act(() => container.querySelector('[aria-label="Contract details"] input[type="checkbox"]').click());
    act(() => {
      fillInput(container.querySelector('#tenantform-name'), 'Pending award');
      fillInput(container.querySelector('#tenantform-type'), 'Office');
    });
    await act(async () => button(container, 'Mark all essential fields Not Available').click());
    expect(container.querySelector('#term-award_reference').disabled).toBe(true);
    expect(container.querySelector('#tenantform-name').disabled).toBe(false);
    await act(async () => button(container, 'Add Allotment').click());
    const [, options] = global.fetch.mock.calls.find(([url, request]) => url === '/api/tenants/' && request.method === 'POST');
    expect(JSON.parse(options.body).contract.unavailable).toEqual(expect.arrayContaining([
      'award_reference', 'letter_issued_on', 'start_date', 'end_date', 'rent_basis',
      'accepted_rate_amount', 'approved_rate_reference',
    ]));
  } finally { close(); }
});
