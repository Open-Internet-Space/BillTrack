
export const formatCurrency = (n) =>
  "₹ " + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatDate = (d) => d ? new Date(d).toLocaleDateString("en-IN") : "—";

export const allotteeLabel = allottee => allottee.display_name || [allottee.name, allottee.allotment_description].filter(Boolean).join(" — ");
