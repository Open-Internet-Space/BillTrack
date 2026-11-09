import { act, fillInput, signedInApp } from "../../test-support/app";

test.each([
  ['Dashboard', ['tenants', 'bills', 'dashboard']],
  ['Allottees', ['tenants']],
  ['Bills', ['bills']],
  ['Payments', ['tenants', 'payments']],
  ['Payment Adjustments', ['tenants', 'bills', 'payments']],
  ['Penalties', ['tenants', 'bills']],
  ['Reports', ['tenants', 'reports']],
])('%s refresh loads fresh section data', async (section, resources) => {
  const { container, close } = await signedInApp(url => url.includes('/reports/')
    ? Promise.resolve({ ok: true, json: async () => ({ title: 'Pending bills', count: 0, columns: [{ key: 'vendor', label: 'Vendor' }],
      rows: [], totals: {}, notes: [], snapshot: 'fresh-report' }) }) : null);
  const button = label => [...container.querySelectorAll('button')].find(node => node.textContent === label);
  const calls = resource => global.fetch.mock.calls.filter(([url]) => url.startsWith(`/api/${resource}/`)).length;
  try {
    if (section !== 'Dashboard') await act(async () => button(section).click());
    const before = resources.map(calls);
    expect(button('↻ Refresh')).toBeDefined();
    await act(async () => button('↻ Refresh').click());
    resources.forEach((resource, index) => expect(calls(resource)).toBeGreaterThan(before[index]));
    expect(container.querySelector('[role="alert"]')).toBeNull();
  } finally { close(); }
});

test.each([false, true])("raising bills omits tentative due date (bulk: %s)", async bulk => {
  const { container, close } = await signedInApp();
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  try {
    await act(async () => button("Bills").click());
    act(() => button("+ Raise Bill").click());
    const dialog = container.querySelector("dialog");
    expect(dialog.textContent).not.toContain("Tentative Due Date");
    expect(dialog.querySelector('input[type="date"]')).toBeNull();
    expect(dialog.textContent).toContain("Pending Receipt");
    if (bulk) {
      act(() => {
        fillInput(dialog.querySelector("#billform-from-month"), "2026-01");
        fillInput(dialog.querySelector("#billform-to-month"), "2026-02");
      });
    }
    await act(async () => button("Raise Bill").click());
    const post = global.fetch.mock.calls.find(([url, options]) => url.includes("/bills/") && options?.method === "POST");
    expect(post).toBeDefined();
    expect(JSON.parse(post[1].body)).not.toHaveProperty("due_date");
  } finally { close(); }
});

test("payment saving prevents repeat submission and preserves input after a validation error", async () => {
  let rejectSave;
  const saveResponse = new Promise(resolve => { rejectSave = resolve; });
  const { container, close } = await signedInApp((url, options) => options.method === "POST" && url.endsWith("/payments/") ? saveResponse : null);
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  await act(async () => button("Bills").click());
  await act(async () => button("Pay").click());
  const dialog = container.querySelector("dialog");
  expect(dialog).not.toBeNull();
  expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
  const amount = [...dialog.querySelectorAll("input")].find(input => [...input.labels].some(label => label.textContent.includes("Principal Amount")));
  expect(amount).toBeDefined();
  act(() => fillInput(amount, "75"));
  act(() => { button("Record Payment").click(); button("Record Payment")?.click(); });
  expect(dialog.querySelector("fieldset").disabled).toBe(true);
  expect(dialog.textContent).toContain("Saving");
  const posts = () => global.fetch.mock.calls.filter(([url, options]) => url.endsWith("/payments/") && options?.method === "POST");
  expect(posts()).toHaveLength(1);
  await act(async () => rejectSave({ ok: false, json: async () => ({ amount: ["Check the amount entered."] }) }));
  expect(dialog.querySelector('[role="alert"]').textContent).toContain("Check the amount entered.");
  expect(amount.value).toBe("75");
  expect(dialog.querySelector("fieldset").disabled).toBe(false);
  act(() => button("Cancel").click());
  close();
});

test("successful payment save returns focus to the stable work area during refresh", async () => {
  const { container, close } = await signedInApp();
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  await act(async () => button("Bills").click());
  act(() => button("Pay").focus());
  await act(async () => button("Pay").click());
  await act(async () => button("Record Payment").click());
  expect(container.querySelector("dialog")).toBeNull();
  expect(document.activeElement).toBe(container.querySelector("main"));
  expect(container.textContent).toContain("Payment recorded");
  close();
});

test("server failure after a payment submission warns to check records before retrying", async () => {
  const { container, close } = await signedInApp((url, options) => options.method === "POST" && url.endsWith("/payments/")
    ? Promise.resolve({ ok: false, status: 500, json: async () => ({ detail: "Service error" }) }) : null);
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  await act(async () => button("Bills").click());
  await act(async () => button("Pay").click());
  await act(async () => button("Record Payment").click());
  expect(container.querySelector('dialog [role="alert"]').textContent).toContain("Check the records before retrying");
  expect(container.querySelector("#paymentform-principal-amount").value).toBe("100");
  close();
});

test("navigation reuses loaded records and refreshes them after a payment save", async () => {
  const { container, close } = await signedInApp();
  expect(container.querySelector('.project-credits')).toBeNull();
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  const calls = path => global.fetch.mock.calls.filter(([url, options]) => url === `/api/${path}/` && !options?.method).length;
  await act(async () => button("Bills").click());
  await act(async () => button("Payments").click());
  await act(async () => button("Bills").click());
  expect(calls("bills")).toBe(1);
  expect(calls("tenants")).toBe(1);
  expect(calls("payments")).toBe(1);
  await act(async () => button("Pay").click());
  await act(async () => button("Record Payment").click());
  expect(calls("bills")).toBe(2);
  await act(async () => button("Payments").click());
  expect(calls("payments")).toBe(2);
  expect(container.querySelector('.project-credits')).toBeNull();
  close();
});

test("cached records expire and dashboard visits refresh payment history", async () => {
  const now = Date.now();
  const clock = jest.spyOn(Date, "now").mockReturnValue(now);
  const { container, close } = await signedInApp();
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  const calls = path => global.fetch.mock.calls.filter(([url, options]) => url === `/api/${path}/` && !options?.method).length;
  try {
    await act(async () => button("Payments").click());
    await act(async () => button("Dashboard").click());
    await act(async () => button("Payments").click());
    expect(calls("payments")).toBe(2);
    clock.mockReturnValue(now + 31000);
    await act(async () => button("Bills").click());
    expect(calls("bills")).toBe(3);
    await act(async () => button("Payments").click());
    expect(calls("payments")).toBe(3);
    clock.mockReturnValue(now);
    await act(async () => button("Bills").click());
    expect(calls("bills")).toBe(4);
  } finally { close(); clock.mockRestore(); }
});

test("a committed payment with a failed response is visible when checking records", async () => {
  let committed = false;
  const { container, close } = await signedInApp((url, options) => {
    if (url.endsWith("/payments/") && options.method === "POST") {
      committed = true;
      return Promise.resolve({ ok: false, status: 500, json: async () => ({ detail: "Response failed" }) });
    }
    if (url.endsWith("/payments/") && committed) return Promise.resolve({ ok: true, json: async () => [{
      id: 1, bill: 1, bill_tenant: 1, bill_tenant_name: "Test Allottee", bill_year: 2026,
      bill_month: 11, bill_period: "Nov 2026", amount: "100.00", penalty_paid: "0.00", receipt_no: "CONFIRMED-RECEIPT"
    }] });
    return null;
  });
  const button = text => [...container.querySelectorAll("button")].find(item => item.textContent === text);
  await act(async () => button("Payments").click());
  await act(async () => button("Bills").click());
  await act(async () => button("Pay").click());
  await act(async () => button("Record Payment").click());
  expect(container.querySelector('dialog [role="alert"]').textContent).toContain("Check the records");
  await act(async () => button("Cancel").click());
  await act(async () => button("Payments").click());
  expect(container.textContent).toContain("CONFIRMED-RECEIPT");
  close();
});
