import { useState, useEffect, useMemo } from "react";

export function BillForm({ tenants, initialTenant, onSave, onClose }) {
  const activeTenants = tenants.filter(t => t.active);
  const selectedTenant = activeTenants.some(t => String(t.id) === String(initialTenant)) ? initialTenant : activeTenants[0]?.id || "";
  const now = new Date();
  const currentPeriod = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [form, setForm] = useState({
    tenant: selectedTenant, from_period: currentPeriod, to_period: currentPeriod,
    rent: "", water: "", gst_treatment: "cgst_sgst", notes: ""
  });
  const [electricRows, setElectricRows] = useState({});
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const parsePeriod = (value) => {
    const [year, month] = String(value || "").split("-").map(Number);
    return { year, month };
  };
  const from = parsePeriod(form.from_period);
  const to = parsePeriod(form.to_period);
  const monthCount = from.year && from.month && to.year && to.month
    ? Math.max(0, (to.year * 12 + to.month) - (from.year * 12 + from.month) + 1)
    : 0;
  const periods = useMemo(() => {
    if (monthCount < 1 || monthCount > 36) return [];
    const rows = [];
    for (let index = from.year * 12 + from.month; index <= to.year * 12 + to.month; index += 1) {
      const year = Math.floor((index - 1) / 12);
      const month = (index - 1) % 12 + 1;
      const key = `${year}-${String(month).padStart(2, "0")}`;
      const label = new Date(year, month - 1, 1).toLocaleString("en-IN", { month: "short", year: "numeric" });
      rows.push({ year, month, key, label });
    }
    return rows;
  }, [monthCount, from.month, from.year, to.month, to.year]);
  useEffect(() => {
    setElectricRows(prev => {
      const next = {};
      periods.forEach(p => {
        next[p.key] = prev[p.key] || { electric: "", electric_reading: "" };
      });
      return next;
    });
  }, [periods]);
  const setElectricRow = (key, field, value) => {
    setElectricRows(prev => ({
      ...prev,
      [key]: { ...(prev[key] || { electric: "", electric_reading: "" }), [field]: value }
    }));
  };
  const submit = () => {
    if (!form.tenant || monthCount < 1 || monthCount > 36) return;
    const monthItems = periods.map(p => ({
      month: p.month,
      year: p.year,
      electric: electricRows[p.key]?.electric || 0,
      electric_reading: electricRows[p.key]?.electric_reading || "",
    }));
    const payload = {
      tenant: form.tenant,
      rent: form.rent || 0,
      water: form.water || 0,
      gst_treatment: form.gst_treatment || "cgst_sgst",
      notes: form.notes || "",
    };

    if (monthCount === 1) {
      onSave({ ...payload, ...monthItems[0] });
      return;
    }

    onSave({
      bulk: true,
      payload: {
        ...payload,
        from_month: from.month,
        from_year: from.year,
        to_month: to.month,
        to_year: to.year,
        month_items: monthItems,
      },
    });
  };

  return (
    <div style={{ width: 680, maxWidth: "100%" }}>
      <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>Raise Bill</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div style={{ gridColumn: "1/-1" }}><label htmlFor="billform-tenant">Allottee</label><select id="billform-tenant" className="inp" value={form.tenant} onChange={e => set("tenant", e.target.value)}>{activeTenants.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        <div><label htmlFor="billform-from-month">From Month</label><input id="billform-from-month" className="inp" type="month" value={form.from_period} onChange={e => set("from_period", e.target.value)} /></div>
        <div><label htmlFor="billform-to-month">To Month</label><input id="billform-to-month" className="inp" type="month" value={form.to_period} onChange={e => set("to_period", e.target.value)} /></div>
        <div><label htmlFor="billform-rent">Rent (₹)</label><input id="billform-rent" className="inp" type="number" value={form.rent} onChange={e => set("rent", e.target.value)} /></div>
        <div><label htmlFor="billform-water">Water (₹)</label><input id="billform-water" className="inp" type="number" value={form.water} onChange={e => set("water", e.target.value)} /></div>
        <div><label htmlFor="billform-gst-type">GST Type</label><select id="billform-gst-type" className="inp" value={form.gst_treatment} onChange={e => set("gst_treatment", e.target.value)}><option value="cgst_sgst">CGST + SGST</option><option value="igst">IGST</option></select></div>
        <p style={{ gridColumn: "1/-1", fontSize: 12, color: "#8b949e", marginTop: 8 }}>The bill stays Pending Receipt with no late-payment penalty until receipt is confirmed through mail.</p>
        {monthCount > 0 && (
          <div style={{ gridColumn: "1/-1", border: "1px solid #30363d", borderRadius: 8, overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "130px 150px 1fr", gap: 10, padding: "9px 12px", background: "#0d1117", color: "#8b949e", fontFamily: "'JetBrains Mono',monospace", fontSize: 11, textTransform: "uppercase" }}>
              <span>Month</span><span>Electric</span><span>Electricity Reading</span>
            </div>
            {periods.map(p => (
              <div key={p.key} style={{ display: "grid", gridTemplateColumns: "130px 150px 1fr", gap: 10, alignItems: "center", padding: "10px 12px", borderTop: "1px solid #21262d" }}>
                <div style={{ color: "#f0a500", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>{p.label}</div>
                <input aria-label={`Electricity amount for ${p.label}`} className="inp" type="number" value={electricRows[p.key]?.electric || ""} onChange={e => setElectricRow(p.key, "electric", e.target.value)} />
                <input aria-label={`Electricity reading for ${p.label}`} className="inp" value={electricRows[p.key]?.electric_reading || ""} placeholder="e.g. Prev 1200, Current 1420, Units 220" onChange={e => setElectricRow(p.key, "electric_reading", e.target.value)} />
              </div>
            ))}
          </div>
        )}
        {monthCount > 1 && (
          <div style={{ gridColumn: "1/-1", background: "#0d1117", border: "1px solid #30363d", borderRadius: 8, padding: "10px 12px", color: "#f0a500", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>
            This will raise {monthCount} separate monthly bills. Rent and water stay common; electricity is saved month-wise.
          </div>
        )}
        {monthCount === 0 && (
          <div style={{ gridColumn: "1/-1", background: "#ef444422", border: "1px solid #ef4444", borderRadius: 8, padding: "10px 12px", color: "#f87171", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>
            To Month must be the same as or after From Month.
          </div>
        )}
        {monthCount > 36 && (
          <div style={{ gridColumn: "1/-1", background: "#ef444422", border: "1px solid #ef4444", borderRadius: 8, padding: "10px 12px", color: "#f87171", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>
            Bulk bill creation is limited to 36 months at a time.
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!form.tenant || monthCount < 1 || monthCount > 36} onClick={submit}>Raise Bill</button>
      </div>
    </div>
  );
}
