import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";

const COLLAPSE_KEY = "sidebar_collapsed";

function readCollapsed() {
  try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
}

export default function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  // Chat thread lives here so it survives switching sidebar tabs.
  const [messages, setMessages] = useState([]);

  function toggle() {
    setCollapsed((c) => {
      try { localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1"); } catch { /* ignore */ }
      return !c;
    });
  }

  return (
    <div className="dashboard">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <main className="dashboard-main">
        <Outlet context={{ messages, setMessages }} />
      </main>
    </div>
  );
}
