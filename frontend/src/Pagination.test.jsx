import { act } from "react";
import { createRoot } from "react-dom/client";
import Pagination, { usePagination } from "./Pagination";

function RecordList({ count }) {
  const pagination = usePagination(Array.from({ length: count }, (_, index) => index + 1));
  return <><Pagination pagination={pagination} label="records" /><output>{pagination.pageRows.join(",")}</output></>;
}

test("pagination clamps after deletion, resets row size, and handles empty records", () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  const root = createRoot(container);
  const button = text => [...container.querySelectorAll('button')].find(item => item.textContent === text);
  try {
    act(() => root.render(<RecordList count={22} />));
    expect(button('Prev').disabled).toBe(true);
    act(() => button('Next').click());
    act(() => button('Next').click());
    expect(container.querySelector('output').textContent).toBe('21,22');
    expect(button('Next').disabled).toBe(true);
    act(() => root.render(<RecordList count={12} />));
    expect(container.textContent).toContain('Showing 11-12 of 12 records');
    act(() => button('Prev').click());
    expect(container.textContent).toContain('Showing 1-10 of 12 records');
    act(() => button('Next').click());
    const size = container.querySelector('select');
    act(() => { size.value = '15'; size.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(container.textContent).toContain('Showing 1-12 of 12 records');
    act(() => root.render(<RecordList count={0} />));
    expect(container.textContent).toContain('Showing 0-0 of 0 records');
    expect(button('Prev').disabled).toBe(true);
    expect(button('Next').disabled).toBe(true);
  } finally { act(() => root.unmount()); }
});
