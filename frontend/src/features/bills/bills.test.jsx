import { act, sampleBill, fillInput, choose, signedInApp } from "../../test-support/app";

test("receipt confirmation calculates five days and sends the actual receipt date", async () => {
  const prompt = jest.spyOn(window, 'prompt').mockReturnValue('Confirm recorded receipt date');
  const { container, close } = await signedInApp();
  try {
    const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
    await act(async () => button("Bills").click());
    await act(async () => button("Confirm Receipt / Update Dispatch").click());
    const receipt = container.querySelector('#billdispatchform-date-of-signature-issue');
    expect([...receipt.labels][0].textContent).toBe("Confirmed Receipt Date (Issue Date)");
    act(() => fillInput(receipt, "2026-10-31"));
    const due = container.querySelector('#billdispatchform-due-date');
    expect(due.value).toBe("2026-11-05");
    expect(due.readOnly).toBe(true);
    expect(container.querySelector('dialog').textContent).toContain("Counting starts the following day");
    act(()=>fillInput(container.querySelector('#billdispatchform-change-reason'),'Confirm recorded receipt date'));
    await act(async () => button("Save Receipt / Dispatch").click());
    const [, options] = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/bills/1/') && options?.method === 'PATCH');
    expect(JSON.parse(options.body)).toMatchObject({ issue_date: "2026-10-31", due_date: "2026-11-05" });
    expect(prompt).not.toHaveBeenCalled();
  } finally { close(); prompt.mockRestore(); }
});

test("pending receipt stays visible in bills but is absent from upcoming due dates", async () => {
  const { container, close } = await signedInApp(url => url.includes('/bills/')
    ? Promise.resolve({ ok: true, json: async () => [{ ...sampleBill, issue_date: null, receipt_status: 'Pending Receipt' }] }) : null);
  try {
    expect(container.querySelector('[aria-label="Upcoming due dates"]').textContent).toContain('No upcoming due dates');
    await act(async () => [...container.querySelectorAll('button')].find(button => button.textContent === 'Bills').click());
    expect(container.querySelector('tbody').textContent).toContain('Pending Receipt');
    expect(container.querySelector('tbody').textContent).toContain('UNPAID');
  } finally { close(); }
});

test("individual and selected-bill printing fetch authorized documents", async () => {
  const popup = { opener: window, closed: false, location: { replace: jest.fn() }, addEventListener: jest.fn(), close: jest.fn() };
  const open = jest.spyOn(window, "open").mockReturnValue(popup);
  const oldCreate = URL.createObjectURL;
  const oldRevoke = URL.revokeObjectURL;
  URL.createObjectURL = jest.fn(() => "blob:invoice");
  URL.revokeObjectURL = jest.fn();
  const { container, close } = await signedInApp(url => url.includes('/invoice/')
    ? Promise.resolve({ ok: true, blob: async () => new Blob(['<html>Invoice</html>'], { type: 'text/html' }) }) : null);
  try {
    const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
    await act(async () => button("Bills").click());
    expect(button("Format 2")).toBeUndefined();
    await act(async () => button("Invoice").click());
    expect(open).toHaveBeenLastCalledWith("about:blank", "_blank");
    expect(popup.opener).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith('/api/invoice/1/', expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Token test-token' }) }));
    expect(popup.location.replace).toHaveBeenCalledWith('blob:invoice');
    popup.addEventListener.mock.calls[0][1]();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:invoice');
    const selected = [...container.querySelectorAll("button")].find(item => item.textContent.includes("Print Selected"));
    act(() => container.querySelector('tbody input[type="checkbox"]').click());
    await act(async () => selected.click());
    expect(global.fetch).toHaveBeenCalledWith('/api/invoice/bulk/?ids=1', expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Token test-token' }) }));
  } finally { close(); open.mockRestore(); URL.createObjectURL = oldCreate; URL.revokeObjectURL = oldRevoke; }
});

test('extension demands share the Bills list and use their own print and receipt actions', async () => {
  const fee = { id: 1, kind: 'extension_fee', tenant: 1, allotment: 7, assessed_on: '2026-12-01',
    register_label: 'Test Allottee', description: 'Extension for second year', authority_reference: 'FEE-REF',
    balance_due: '900.00', gross_amount: '1000.00', amount_paid: '100.00', status: 'Partial' };
  const reply = data => Promise.resolve({ ok: true, json: async () => data });
  const popup = { closed: false, location: { replace: jest.fn() }, addEventListener: jest.fn() };
  const open = jest.spyOn(window, 'open').mockReturnValue(popup);
  const oldCreate = URL.createObjectURL;
  URL.createObjectURL = jest.fn(() => 'blob:extension');
  const { container, close } = await signedInApp(url => {
    if (url.endsWith('/estate-charges/?kind=extension_fee')) return reply([fee]);
    if (url.endsWith('/estate-charges/1/demand/')) return Promise.resolve({ ok: true, blob: async () => new Blob(['Demand']) });
    return null;
  });
  try {
    const button = (root, label) => [...root.querySelectorAll('button')].find(node => node.textContent === label);
    await act(async () => button(container, 'Bills').click());
    const [demand, monthly] = container.querySelectorAll('tbody tr');
    expect(demand.textContent).toContain('Extension for second year');
    expect(demand.textContent).toContain('900.00');
    expect(monthly.textContent).toContain('TEST-1');
    act(() => container.querySelector('[aria-label="Select all bills"]').click());
    expect(button(container, 'Print Selected (1)')).toBeDefined();
    await act(async () => button(demand, 'Print extension fee demand').click());
    expect(global.fetch).toHaveBeenCalledWith('/api/estate-charges/1/demand/', expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Token test-token' }) }));
    expect(popup.location.replace).toHaveBeenCalledWith('blob:extension');
    await act(async () => button(demand, 'Record charge receipt').click());
    expect(container.querySelector('form[aria-label="Charge receipt"]')).not.toBeNull();
    await act(async () => button(container.querySelector('dialog'), 'Cancel').click());
    act(() => choose(container.querySelector('#bills-status'), 'Partial'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody').textContent).toContain('Extension fee demand');
  } finally { close(); open.mockRestore(); URL.createObjectURL = oldCreate; }
});

test.each([true, false])('printing handles blocked windows or failed requests (blocked: %s)', async blocked => {
  const popup = { opener: window, close: jest.fn() };
  const open = jest.spyOn(window, 'open').mockReturnValue(blocked ? null : popup);
  const { container, close } = await signedInApp(url => url.includes('/invoice/') ? Promise.resolve({ ok: false, status: 401, json: async () => ({ detail: 'Invalid token.' }) }) : null);
  try {
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent === 'Bills').click());
    await act(async () => [...container.querySelectorAll('button')].find(node => node.textContent === 'Invoice').click());
    expect(container.textContent).toContain(blocked ? 'Allow pop-ups' : 'sign-in has expired');
    if (!blocked) expect(popup.close).toHaveBeenCalled();
  } finally { close(); open.mockRestore(); }
});

test('raise bill requires a current server preview and sends holiday dates with the shop term', async () => {
  const { container, close } = await signedInApp((url, options) => {
    if (url.includes('/allotments/')) return Promise.resolve({ ok: true, json: async () => [
      { id: 7, tenant: 1, shop_code: 'A-101', start_date: '2020-01-01', effective_end: '2100-12-31' }] });
    if (url.endsWith('/bills/preview/')) return Promise.resolve({ ok: true, json: async () => ({ months: [
      { year: 2026, month: 6, month_name: 'Jun', full_month_rent: '3000.00', rent: '2000.00',
        holiday_closed_days: 10, days_in_month: 30, holiday_waiver: '1000.00', gst_on_rent: '360.00',
        total_amount: '2360.00', already_exists: false }] }) });
    return null;
  });
  try {
    const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
    await act(async () => button('Bills').click());
    await act(async () => button('+ Raise Bill').click());
    expect(container.querySelector('#billform-allotment').value).toBe('7');
    expect(button('Raise Bill').disabled).toBe(true);
    act(() => { fillInput(container.querySelector('#billform-from-month'), '2026-06');
      fillInput(container.querySelector('#billform-to-month'), '2026-06');
      fillInput(container.querySelector('#billform-rent'), '3000');
      fillInput(container.querySelector('#billform-holiday-start'), '2026-06-10');
      fillInput(container.querySelector('#billform-holiday-end'), '2026-06-19'); });
    await act(async () => button('Preview monthly amounts').click());
    expect(container.querySelector('[aria-label="Monthly rent preview"]').textContent).toContain('10 / 30');
    expect(button('Raise Bill').disabled).toBe(false);
    act(() => fillInput(container.querySelector('#billform-water'), '50'));
    expect(button('Raise Bill').disabled).toBe(true);
    await act(async () => button('Preview monthly amounts').click());
    await act(async () => button('Raise Bill').click());
    const save = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/bills/') && options?.method === 'POST');
    expect(JSON.parse(save[1].body)).toMatchObject({ allotment: 7, billing_category: 'allotment', full_month_rent: '3000',
      holiday_start_date: '2026-06-10', holiday_end_date: '2026-06-19', water: '50' });
  } finally { close(); }
});

test('raise bill offers an explicit explained non-shop category when no term is recorded', async () => {
  const { container, close } = await signedInApp();
  try {
    const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
    await act(async () => button('Bills').click());
    await act(async () => button('+ Raise Bill').click());
    expect(container.textContent).toContain('No allotment covers this billing range');
    expect(button('Preview monthly amounts').disabled).toBe(true);
    act(() => choose(container.querySelector('#billform-category'), 'other'));
    expect(container.querySelector('#billform-allotment')).toBeNull();
    expect(button('Preview monthly amounts').disabled).toBe(true);
  } finally { close(); }
});

test('editing a holiday bill starts from full rent and clearing dates restores the original basis', async () => {
  const prompt = jest.spyOn(window, 'prompt').mockReturnValue('Correct holiday closure');
  const { container, close } = await signedInApp((url, options) => {
    if (url.endsWith('/bills/1/preview/')) return Promise.resolve({ ok: true, json: async () => ({ months: [
      { year: 2026, month: 6, month_name: 'Jun', rent: '3000.00', holiday_closed_days: 0,
        days_in_month: 30, holiday_waiver: '0.00', gst_on_rent: '0.00', total_amount: '3000.00' }] }) });
    if (url.includes('/bills/') && options.method !== 'PATCH') return Promise.resolve({ ok: true, json: async () => [
      { ...sampleBill, month: 6, month_name: 'Jun', rent: '2000.00', full_month_rent: '3000.00',
        holiday_start_date: '2026-06-10', holiday_end_date: '2026-06-19' }] });
    return null;
  });
  try {
    const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
    await act(async () => button('Bills').click());
    await act(async () => button('Edit').click());
    expect(container.querySelector('#billeditform-rent').value).toBe('3000.00');
    act(() => { fillInput(container.querySelector('#billeditform-holiday-start'), '');
      fillInput(container.querySelector('#billeditform-holiday-end'), ''); });
    act(()=>fillInput(container.querySelector('#billeditform-change-reason'),'Correct holiday closure'));
    expect(button('Save Changes').disabled).toBe(true);
    await act(async () => button('Preview monthly amounts').click());
    expect(button('Save Changes').disabled).toBe(false);
    await act(async () => button('Save Changes').click());
    const save = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/bills/1/') && options?.method === 'PATCH');
    expect(JSON.parse(save[1].body)).toMatchObject({ full_month_rent: '3000.00', holiday_start_date: null, holiday_end_date: null });
    expect(prompt).not.toHaveBeenCalled();
  } finally { close(); prompt.mockRestore(); }
});

test('notice dispatch records India time and previews the seven-day deadline without a legacy receipt date', async () => {
  const prompt = jest.spyOn(window, 'prompt').mockReturnValue('Record verified email evidence');
  const { container, close } = await signedInApp((url, options) => {
    if (url.endsWith('/bills/1/preview/')) return Promise.resolve({ ok: true, json: async () => ({ months: [
      { due_date: '2026-11-08', receipt_status: 'Email Dispatch Confirmed' }] }) });
    if (url.includes('/bills/') && options.method !== 'PATCH') return Promise.resolve({ ok: true, json: async () => [
      { ...sampleBill, billing_policy: 'notices_368_369', raised_date: '2026-11-01', issue_date: null,
        due_date: '2026-11-08', receipt_status: 'Pending Email Dispatch' }] });
    return null;
  });
  try {
    const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
    await act(async () => button('Bills').click());
    await act(async () => button('Record email dispatch').click());
    expect(container.querySelector('#billdispatchform-date-of-signature-issue')).toBeNull();
    act(() => {
      fillInput(container.querySelector('#notice-dispatch-time'), '2026-11-10T15:30');
      fillInput(container.querySelector('#notice-dispatch-recipient'), 'synthetic@example.invalid');
      fillInput(container.querySelector('#notice-dispatch-reference'), 'Verified message 123');
      container.querySelector('#notice-dispatch-confirmed').click();
      fillInput(container.querySelector('#notice-change-reason'),'Record verified email evidence');
    });
    await act(async () => button('Preview deadline').click());
    expect(container.querySelector('[aria-label="Notice deadline preview"]').textContent).toContain('8/11/2026');
    await act(async () => button('Save notice dates / dispatch').click());
    const save = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/bills/1/') && options?.method === 'PATCH');
    expect(JSON.parse(save[1].body)).toMatchObject({ raised_date: '2026-11-01',
      email_dispatched_at: '2026-11-10T10:00:00.000Z', dispatch_recipient: 'synthetic@example.invalid',
      dispatch_message_reference: 'Verified message 123' });
    expect(JSON.parse(save[1].body)).not.toHaveProperty('issue_date');
    expect(prompt).not.toHaveBeenCalled();
  } finally { close(); prompt.mockRestore(); }
});

test('notice bill can use approved monthly rates and records the explicit raised date', async () => {
  const { container, close } = await signedInApp((url, options) => {
    if (url.includes('/allotments/')) return Promise.resolve({ok:true,json:async()=>[
      {id:7,tenant:1,shop_code:'A-101',notice_governed:true,start_date:'2020-01-01',effective_end:'2100-12-31'}]});
    if (url.endsWith('/bills/preview/')) return Promise.resolve({ok:true,json:async()=>({months:[
      {year:2026,month:11,month_name:'Nov',billing_policy:'notices_368_369',full_month_rent:'1890.00',rent:'1890.00',
        rate_snapshot:'12.6000',area_snapshot:'150.0000',rent_revision_reference:'April approval',
        rate_warnings:[],due_date:'2026-11-08',already_exists:false}]})});
    return null;
  });
  try {
    const button = text => [...container.querySelectorAll('button')].find(item=>item.textContent===text);
    await act(async()=>button('Bills').click());
    await act(async()=>button('+ Raise Bill').click());
    act(()=>fillInput(container.querySelector('#billform-raised'),'2026-11-01'));
    await act(async()=>button('Preview monthly amounts').click());
    expect(container.querySelector('[aria-label="Monthly rent preview"]').textContent).toContain('12.6000');
    await act(async()=>button('Raise Bill').click());
    const save=global.fetch.mock.calls.find(([url,options])=>url.endsWith('/bills/')&&options?.method==='POST');
    expect(JSON.parse(save[1].body)).toHaveProperty('raised_date','2026-11-01');
    expect(JSON.parse(save[1].body)).not.toHaveProperty('full_month_rent');
  } finally {close();}
});


test.each([false, true])('area × rate supplies rounded full rent to preview and save (bulk: %s)', async bulk => {
  const { container, close } = await signedInApp(url => {
    if (url.endsWith('/allotments/')) return Promise.resolve({ ok: true, json: async () => [
      { id: 7, tenant: 1, start_date: '2020-01-01', effective_end: '2100-12-31' }] });
    if (url.endsWith('/bills/preview/')) return Promise.resolve({ ok: true, json: async () => ({ months: [
      { year: 2026, month: 6, full_month_rent: '10.08', already_exists: false }] }) });
    return null;
  });
  const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
  const input = name => container.querySelector(`#billform-${name}`);
  try {
    await act(async () => button('Bills').click());
    await act(async () => button('+ Raise Bill').click());
    act(() => {
      fillInput(input('from-month'), '2026-06');
      fillInput(input('to-month'), bulk ? '2026-07' : '2026-06');
      fillInput(input('rent'), '800');
      choose(input('rent-method'), 'calculated');
    });
    act(() => fillInput(input('rent-area'), '1'));
    expect(input('rent')).toBeNull();
    expect(button('Preview monthly amounts').disabled).toBe(true);
    act(() => fillInput(input('rent-rate'), '10.0750'));
    expect(container.querySelector('output').textContent).toContain('10.08');
    await act(async () => button('Preview monthly amounts').click());
    const findPost = path => JSON.parse(global.fetch.mock.calls.find(([url, options]) =>
      url === path && options.method === 'POST')[1].body);
    expect(findPost('/api/bills/preview/')).toMatchObject({ full_month_rent: '10.08' });
    act(() => choose(input('rent-method'), 'direct'));
    expect(input('rent').value).toBe('800');
    expect(input('rent-area')).toBeNull();
    expect(button('Raise Bill').disabled).toBe(true);
    act(() => choose(input('rent-method'), 'calculated'));
    await act(async () => button('Raise Bill').click());
    const saved = findPost(bulk ? '/api/bills/bulk-create/' : '/api/bills/');
    expect(saved).toMatchObject({ full_month_rent: '10.08' });
    expect(saved).not.toHaveProperty('rent_area');
    expect(saved).not.toHaveProperty('rent_rate');
  } finally { close(); }
});


test('edit bill can replace full-month rent with a calculation while preserving closure dates', async () => {
  const { container, close } = await signedInApp((url, options) => {
    if (url.endsWith('/bills/1/preview/')) return Promise.resolve({ ok: true, json: async () => ({ months: [
      { year: 2026, month: 11, full_month_rent: '1500.00', rent: '1450.00' }] }) });
    if (url.endsWith('/bills/') && !options.method) return Promise.resolve({ ok: true, json: async () => [
      { ...sampleBill, rent: '100.00', holiday_start_date: '2026-11-10', holiday_end_date: '2026-11-10' }] });
    return null;
  });
  const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
  const input = name => container.querySelector(`#billeditform-${name}`);
  try {
    await act(async () => button('Bills').click());
    await act(async () => button('Edit').click());
    act(() => choose(input('rent-method'), 'calculated'));
    act(() => {
      fillInput(input('rent-area'), '150');
      fillInput(input('rent-rate'), '10');
      fillInput(input('change-reason'), 'Correct area-based rent');
    });
    await act(async () => button('Preview monthly amounts').click());
    await act(async () => button('Save Changes').click());
    const [, options] = global.fetch.mock.calls.find(([url, options]) =>
      url.endsWith('/bills/1/') && options.method === 'PATCH');
    expect(JSON.parse(options.body)).toMatchObject({
      full_month_rent: '1500.00', holiday_start_date: '2026-11-10', holiday_end_date: '2026-11-10',
      change_reason: 'Correct area-based rent'
    });
  } finally { close(); }
});


test.each(['Bills', 'Payments', 'Payment Adjustments'])('%s can correct a receipt in place', async page => {
  const payment = { id: 13, bill: 1, bill_tenant: 1, bill_tenant_name: 'Test Allottee', bill_invoice: 'TEST-1',
    payment_date: '2026-11-11', amount: '50.00', penalty_paid: '0.00', receipt_no: 'ORIGINAL', source: 'receipt' };
  const reply = data => Promise.resolve({ ok: true, json: async () => data });
  const { container, close } = await signedInApp(url => url.startsWith('/api/payments/')
    ? reply(url.endsWith('/payments/13/') ? payment : [payment]) : null);
  const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
  try {
    await act(async () => button(page).click());
    if (page === 'Bills') {
      const receipts = button('Payment receipts');
      expect(receipts.closest('td').cellIndex).toBe(1);
      await act(async () => receipts.click());
    }
    if (page === 'Payment Adjustments') act(() => choose(container.querySelector('#adjustment-vendor'), '1'));
    const edit = button('Edit receipt');
    if (page !== 'Bills') expect(edit.closest('td').cellIndex).toBe(page === 'Payments' ? 0 : 1);
    await act(async () => edit.click());
    const reference = container.querySelector('#paymentform-receipt-no');
    expect(reference.value).toBe('ORIGINAL');
    expect(button('Save receipt').disabled).toBe(true);
    act(() => {
      fillInput(reference, 'CORRECTED');
      fillInput(container.querySelector('#paymentform-reason'), 'Correct ref from actual receipt');
    });
    await act(async () => button('Save receipt').click());
    const [, call] = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/payments/13/') && options.method === 'PATCH');
    expect(JSON.parse(call.body)).toMatchObject({ receipt_no: 'CORRECTED', change_reason: 'Correct ref from actual receipt' });
    expect(JSON.parse(call.body)).not.toHaveProperty('bill');
  } finally { close(); }
});
