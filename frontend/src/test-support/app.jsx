import { act } from "react";

import { createRoot } from "react-dom/client";

import App from "../App";

import { PaymentAdjustments } from "../features/payments/PaymentAdjustments";

import { Payments } from "../features/payments/Payments";

const sampleTenant = { id: 1, name: "Test Allottee", active: true, type: "Shop" };

const sampleBill = { id: 1, tenant: 1, tenant_name: "Test Allottee", invoice_no: "TEST-1", year: 2026, month: 11, month_name: "Nov", issue_date: "2026-10-20", receipt_status: "Receipt Confirmed", due_date: "2099-11-30", status: "Unpaid", balance_due: "100.00", penalty: "5.00", days_overdue: 0 };

const fillInput = (input, value) => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
};

const choose = (select, value) => {
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
};

async function signedInApp(extraFetch) {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  global.fetch = jest.fn(async (url, options = {}) => {
    const override = extraFetch?.(url, options);
    if (override) return override;
    const data = url.includes("/auth/me/") ? { username: "tester" }
      : url.includes("/auth/") ? { token: "test-token", user: { username: "tester" } }
      : url.includes("/dashboard/") ? { total_billed: 100, total_outstanding: 100 }
      : url.includes("/tenants/") ? [sampleTenant]
      : url.includes("/bills/") ? [sampleBill] : [];
    return { ok: true, json: async () => data };
  });
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => root.render(<App />));
  if (container.querySelector(".login-panel")) {
    await act(async () => container.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  }
  return { container, close: () => { act(() => root.unmount()); container.remove(); } };
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});

afterEach(() => { delete global.fetch; localStorage.clear(); });

export { act, createRoot, App, PaymentAdjustments, Payments, sampleTenant, sampleBill, fillInput, choose, signedInApp };
