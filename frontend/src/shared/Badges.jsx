
export const StatusBadge = ({ status }) => {
  const map = { Paid: "#22c55e", Settled: "#22c55e", Waived: "#9ca3af", Unpaid: "#f87171", Partial: "#f59e0b" };
  return (
    <span style={{
      background: map[status] + "22", color: map[status],
      border: `1px solid ${map[status]}44`,
      padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
      letterSpacing: "0.05em", fontFamily: "'JetBrains Mono', monospace"
    }}>{status.toUpperCase()}</span>
  );
};

export const TypeBadge = ({ type }) => {
  const map = { Shop: ["#60a5fa", "🏪"], Canteen: ["#c4b5fd", "🍽️"], Contractor: ["#fdba74", "🏗️"] };
  const [c, icon] = map[type] || ["#9ca3af", "•"];
  return (
    <span style={{
      background: c + "18", color: c, border: `1px solid ${c}30`,
      padding: "3px 9px", borderRadius: 20, fontSize: 12, fontWeight: 600
    }}>{icon} {type}</span>
  );
};
