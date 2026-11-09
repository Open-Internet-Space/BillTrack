import { act, sampleBill, fillInput, signedInApp } from "../../test-support/app";

test("receipt confirmation calculates five days and sends the actual receipt date", async () => {
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
    await act(async () => button("Save Receipt / Dispatch").click());
    const [, options] = global.fetch.mock.calls.find(([url, options]) => url.endsWith('/bills/1/') && options?.method === 'PATCH');
    expect(JSON.parse(options.body)).toMatchObject({ issue_date: "2026-10-31", due_date: "2026-11-05" });
  } finally { close(); }
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
