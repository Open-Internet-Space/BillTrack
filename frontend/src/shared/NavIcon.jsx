
export const navIconPaths = {
  dashboard: "M3 3h7v7H3z M14 3h7v4h-7z M14 11h7v10h-7z M3 14h7v7H3z",
  shops: "M3 10l2-7h14l2 7 M3 10h18 M5 10v11h14V10 M9 21v-7h6v7",
  allotments: "M5 4h14v17H5z M9 2v4 M15 2v4 M5 9h14 M9 13h2 M14 13h2 M9 17h2",
  tenants: "M4 21V5l8-2 8 2v16 M2 21h20 M9 21v-5h6v5 M8 8h1 M15 8h1 M8 12h1 M15 12h1",
  bills: "M6 3h12v18l-3-2-3 2-3-2-3 2V3z M9 7h6 M9 11h6 M9 15h3",
  payments: "M3 5h18v14H3z M3 9h18 M7 14h3",
  adjustments: "M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-2 2 M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l2-2",
  penalty: "M12 3L2 21h20L12 3z M12 9v5 M12 17h.01",
  drafts: "M3 5h18v14H3z M3 5l9 7 9-7",
  reports: "M5 3h10l4 4v14H5z M14 3v5h5 M9 12h6 M9 16h6",
  knowledge: "M12 6C9 4 6 4 3 5v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1z M12 6v14",
};

export const NavIcon = ({ name }) => <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={navIconPaths[name]} /></svg>;
