export const matchesSearch = (query, ...values) => values.some(value =>
  String(value ?? "").toLowerCase().includes(query.trim().toLowerCase()));

export const withinDates = (value, from, to) => (!from && !to)
  || (Boolean(value) && (!from || value >= from) && (!to || value <= to));

export default function FilterBar({ label, onReset, children }) {
  return <div className="card record-filters" role="group" aria-label={label}>
    {children}
    <button type="button" className="btn-ghost" onClick={onReset}>Reset</button>
  </div>;
}
