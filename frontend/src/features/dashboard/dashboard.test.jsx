import { act, signedInApp } from "../../test-support/app";

test("dashboard keeps pagination without search or filter controls", async () => {
  const { container, close } = await signedInApp();
  try {
    expect(container.querySelector('#dashboard-search')).toBeNull();
    expect(container.querySelector('#dashboard-type')).toBeNull();
    expect(container.querySelector('input[type="search"]')).toBeNull();
    expect(container.querySelector('[aria-label="overdue allottees pagination"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="upcoming bills pagination"]')).not.toBeNull();
  } finally { close(); }
});

test("dashboard upcoming bill opens the matching tenant and invoice context", async () => {
  const { container, close } = await signedInApp();
  const entry = [...container.querySelectorAll("button")].find(button => button.textContent.includes("TEST-1"));
  expect(entry).toBeDefined();
  await act(async () => entry.click());
  expect(container.querySelector("h1").textContent).toBe("Bills");
  expect(container.textContent).toContain("TEST-1");
  const tenantFilter = [...container.querySelectorAll("select")].find(select => [...select.labels].some(label => label.textContent === "Allottee"));
  expect(tenantFilter.value).toBe("1");
  close();
});

test("failed dashboard loading provides a retry that recovers", async () => {
  let fail = true;
  const { container, close } = await signedInApp(url => url.includes("/dashboard/") && fail
    ? Promise.resolve({ ok: false, json: async () => ({ detail: "Service unavailable" }) }) : null);
  expect(container.querySelector('[role="alert"]').textContent).toContain("Service unavailable");
  fail = false;
  await act(async () => [...container.querySelectorAll("button")].find(button => button.textContent === "Retry").click());
  expect(container.querySelector("h1").textContent).toBe("Dashboard");
  expect(container.querySelector('[role="alert"]')).toBeNull();
  close();
});
