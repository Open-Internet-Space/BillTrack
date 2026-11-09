import { act, createRoot, PaymentAdjustments, Payments, sampleBill, fillInput, choose } from "../../test-support/app";

test("payment filters use receipt search and inclusive actual payment dates", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement('div');
  const root = createRoot(container);
  const payments = ['2026-11-01', '2026-11-05', '2026-11-06', null, ''].map((date, index) => ({
    id: index + 1, bill: 1, bill_tenant: 1, bill_tenant_name: 'Allottee', bill_invoice: 'INV',
    bill_year: 2025, bill_month: 1, receipt_no: `REC-${index + 1}`, payment_date: date, amount: '10', penalty_paid: '0',
  }));
  act(() => root.render(<Payments payments={payments} />));
  try {
    act(() => fillInput(container.querySelector('#payments-to'), '2026-11-05'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
    act(() => fillInput(container.querySelector('#payments-from'), '2026-11-01'));
    act(() => fillInput(container.querySelector('#payments-search'), 'rec-2'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody').textContent).toContain('REC-2');
    act(() => [...container.querySelectorAll('button')].find(button => button.textContent === 'Reset').click());
    expect(container.querySelectorAll('tbody tr')).toHaveLength(5);
  } finally { act(() => root.unmount()); }
});

test("adjustment filtering preserves original split numbers and full bill totals", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement('div');
  const root = createRoot(container);
  const bills = [{ ...sampleBill, total_amount: '100', amount_paid: '75', penalty_paid: '0' }];
  const payments = [1, 2].map(index => ({ id: index, bill: 1, bill_tenant: 1, bill_tenant_name: 'Allottee',
    bill_invoice: 'TEST-1', bill_year: 2026, bill_month: 11, receipt_no: `REC-${index}`,
    payment_date: `2026-11-0${index}`, amount: index === 1 ? '25' : '50', penalty_paid: '0',
  }));
  act(() => root.render(<PaymentAdjustments bills={bills} payments={payments} />));
  try {
    act(() => choose(container.querySelector('#adjustment-vendor'), '1'));
    act(() => fillInput(container.querySelector('#adjustments-search'), 'rec-2'));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody').textContent).toContain('2 of 2');
    expect(container.textContent).toContain('₹ 75.00');
    expect(container.textContent).toContain('bill totals include all payments');
  } finally { act(() => root.unmount()); }
});

test("adjustments paginate bills and each bill's split payments independently", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement('div');
  const root = createRoot(container);
  const bills = Array.from({ length: 12 }, (_, index) => ({ ...sampleBill, id: index + 1, invoice_no: `INV-${index + 1}` }));
  const payments = bills.flatMap(bill => Array.from({ length: 12 }, (_, index) => ({
    id: bill.id * 100 + index, bill: bill.id, bill_tenant: 1, bill_tenant_name: 'Allottee',
    bill_invoice: bill.invoice_no, amount: '1', penalty_paid: '0', receipt_no: `REC-${bill.id}-${index + 1}`,
  })));
  act(() => root.render(<PaymentAdjustments payments={payments} bills={bills} />));
  try {
    const vendor = container.querySelector('select');
    act(() => { vendor.value = '1'; vendor.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(container.querySelectorAll('tbody')).toHaveLength(10);
    const firstBill = container.querySelector('table').parentElement;
    expect(firstBill.querySelectorAll('tbody tr')).toHaveLength(10);
    const splitsPager = firstBill.querySelector('[aria-label="payments pagination"]');
    act(() => [...splitsPager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    expect(firstBill.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(firstBill.textContent).toContain('11 of 12');
    const billsPager = container.querySelector('[aria-label="bills pagination"]');
    act(() => [...billsPager.querySelectorAll('button')].find(button => button.textContent === 'Next').click());
    expect(container.querySelectorAll('tbody')).toHaveLength(2);
  } finally { act(() => root.unmount()); }
});

test("payment register paginates and filters by vendor", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  const root = createRoot(container);
  const payments = Array.from({ length: 12 }, (_, index) => ({
    id: index + 1,
    bill: index + 1,
    bill_invoice: `INV-${index + 1}`,
    bill_tenant: index === 11 ? 2 : 1,
    bill_tenant_name: index === 11 ? "Other" : "Test",
    bill_year: index === 11 ? 2025 : 2026,
    bill_month: index === 11 ? 10 : 11,
    bill_period: index === 11 ? "Oct 2025" : "Nov 2026",
    amount: "10.00",
    penalty_paid: "0.00",
    payment_date: "2026-11-04",
  }));

  act(() => root.render(<Payments payments={payments} />));
  expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  expect(container.textContent).toContain("Showing 1-10 of 12 payments");

  const next = [...container.querySelectorAll("button")].find(button => button.textContent === "Next");
  act(() => next.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  expect(container.querySelectorAll("tbody tr")).toHaveLength(2);

  const vendor = container.querySelector("select");
  act(() => {
    vendor.value = "2";
    vendor.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(container.textContent).toContain("Showing 1-1 of 1 payments");

  const year = container.querySelectorAll("select")[1];
  act(() => {
    year.value = "2026";
    year.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(container.querySelectorAll("tbody tr")).toHaveLength(0);

  const reset = [...container.querySelectorAll("button")].find(button => button.textContent === "Reset");
  act(() => reset.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  const month = container.querySelectorAll("select")[2];
  act(() => {
    month.value = "10";
    month.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  act(() => root.unmount());
});

test("vendor adjustments group split payments under their bill with amounts", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  const root = createRoot(container);
  const bills = [
    { id: 1, invoice_no: "INV-1", issue_date: "2026-11-03", dispatch_ref_no: "DIS-1", total_amount: "200.00", amount_paid: "150.00", penalty_paid: "5.00", balance_due: "50.00" },
    { id: 2, invoice_no: "INV-2", issue_date: "2026-11-02", dispatch_ref_no: "DIS-2" },
  ];
  const payments = [
    { id: 1, bill: 1, bill_tenant: 1, bill_tenant_name: "Vendor A", bill_invoice: "INV-1", payment_date: "2026-11-04", receipt_no: "REC-1", amount: "100.00", penalty_paid: "0.00" },
    { id: 3, bill: 1, bill_tenant: 1, bill_tenant_name: "Vendor A", bill_invoice: "INV-1", payment_date: "2026-11-06", receipt_no: "REC-3", amount: "50.00", penalty_paid: "5.00" },
    { id: 2, bill: 2, bill_tenant: 2, bill_tenant_name: "Vendor B", bill_invoice: "INV-2", payment_date: "2026-11-05", receipt_no: "REC-2", amount: "200.00", penalty_paid: "0.00" },
  ];

  act(() => root.render(<PaymentAdjustments payments={payments} bills={bills} />));
  expect(container.textContent).not.toContain("REC-1");
  const vendor = container.querySelector("select");
  act(() => {
    vendor.value = "1";
    vendor.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(container.textContent).toContain("INV-1");
  expect(container.textContent).toContain("DIS-1");
  expect(container.textContent).toContain("REC-1");
  expect(container.textContent).toContain("REC-3");
  expect(container.textContent).toContain("1 of 2");
  expect(container.textContent).toContain("2 of 2");
  expect(container.textContent.match(/INV-1/g)).toHaveLength(1);
  expect(container.textContent).toContain("Adjusted principal");
  expect(container.textContent).toContain("₹ 150.00");
  expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
  expect(container.textContent).toContain(new Date("2026-11-03").toLocaleDateString("en-IN"));
  expect(container.textContent).toContain(new Date("2026-11-04").toLocaleDateString("en-IN"));
  expect(container.textContent).not.toContain("REC-2");
  act(() => root.unmount());
});
