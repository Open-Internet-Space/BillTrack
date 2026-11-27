import { formatCurrency } from "../../shared/format";

function rentUnits(value) {
  const match = /^(\d{0,8})(?:\.(\d{0,4}))?$/.exec(value);
  if (!match || !(match[1] || match[2])) return null;
  return window.BigInt(match[1] + (match[2] || "").padEnd(4, "0"));
}

export function calculateFullMonthRent(area, rate) {
  const areaUnits = rentUnits(area);
  const rateUnits = rentUnits(rate);
  if (areaUnits === null || areaUnits === 0n || rateUnits === null) return null;
  // Multiplying two four-place values gives eight decimal places. Round half up to paise.
  const paise = (areaUnits * rateUnits + 500000n) / 1000000n;
  if (paise > 9999999999n) return null;
  return `${paise / 100n}.${String(paise % 100n).padStart(2, "0")}`;
}

export function RentEntryFields({ prefix, method, form, directRent, directField, calculatedRent, approved, set }) {
  return <>
    <div style={{ gridColumn: "1/-1" }}>
      <label htmlFor={`${prefix}-rent-method`}>Monthly rent entry</label>
      <select id={`${prefix}-rent-method`} className="inp" value={method} onChange={e => set("rent_method", e.target.value)}>
        <option value="direct">Enter monthly rent directly</option>
        <option value="calculated">Calculate from area × rate</option>
        {approved && <option value="approved">Use approved rate schedule</option>}
      </select>
    </div>
    {method === "direct" && <div>
      <label htmlFor={`${prefix}-rent`}>Full-month rent (₹)</label>
      <input id={`${prefix}-rent`} className="inp" type="number" min="0" step="0.01"
        value={directRent} onChange={e => set(directField, e.target.value)} />
    </div>}
    {method === "calculated" && <>
      <div>
        <label htmlFor={`${prefix}-rent-area`}>Area allotted (sq ft)</label>
        <input id={`${prefix}-rent-area`} className="inp" type="number" min="0.0001" step="0.0001"
          value={form.rent_area} onChange={e => set("rent_area", e.target.value)} />
      </div>
      <div>
        <label htmlFor={`${prefix}-rent-rate`}>Monthly rate (₹ per sq ft)</label>
        <input id={`${prefix}-rent-rate`} className="inp" type="number" min="0" step="0.0001"
          value={form.rent_rate} onChange={e => set("rent_rate", e.target.value)} />
      </div>
      <p className="form-feedback" style={{ gridColumn: "1/-1" }}>
        <output aria-label="Calculated full-month rent" htmlFor={`${prefix}-rent-area ${prefix}-rent-rate`}>
          {calculatedRent !== null ? `Full-month rent ${formatCurrency(calculatedRent)}`
            : form.rent_area && form.rent_rate
              ? "Use a positive area and a nonnegative rate with up to four decimal places. Full-month rent must be less than ₹10 crore."
              : "Enter the area and rate to calculate the full-month rent."}
        </output>
      </p>
    </>}
  </>;
}
