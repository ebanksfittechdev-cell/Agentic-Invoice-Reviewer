import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { ChatIcon, CollapseIcon, HistoryIcon, LogoMark, UploadIcon } from "./Icons.jsx";
import "./Sidebar.css";

const NAV_ITEMS = [
  { to: "/", label: "Chat", icon: ChatIcon, end: true },
  { to: "/upload-history", label: "Upload history", icon: UploadIcon },
  { to: "/history", label: "View history", icon: HistoryIcon },
];

export default function Sidebar({ collapsed, onToggle }) {
  const { user } = useAuth();
  const initial = (user?.store_name || "?").trim().charAt(0).toUpperCase();

  return (
    <aside className={`sidebar ${collapsed ? "is-collapsed" : ""}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <span className="sidebar-logo"><LogoMark size={18} /></span>
          <span className="sidebar-label sidebar-brand-name">Invoice Reviewer</span>
        </div>
        <button className="sidebar-icon-btn" onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand" : "Collapse"}>
          <CollapseIcon size={18} />
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Main">
        {NAV_ITEMS.map(({ to, label, icon: IconCmp, end }) => (
          <NavLink key={to} to={to} end={end} title={collapsed ? label : undefined}
            className={({ isActive }) => `sidebar-link ${isActive ? "is-active" : ""}`}>
            <IconCmp size={19} />
            <span className="sidebar-label">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user" title={collapsed ? user?.store_name : undefined}>
          <span className="sidebar-avatar">{initial}</span>
          <span className="sidebar-label sidebar-user-text">
            <span className="sidebar-user-name">{user?.store_name}</span>
            <span className="sidebar-user-email">{user?.email}</span>
          </span>
        </div>
      </div>
    </aside>
  );
}
