import { useState } from "react";
import "./login.css";

export default function LoginPage() {
  const [mode, setMode] = useState("login"); // "login" | "register"

  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({
    email: "",
    password: "",
    store_name: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleLoginChange(e) {
    setLoginForm({ ...loginForm, [e.target.name]: e.target.value });
  }

  function handleRegisterChange(e) {
    setRegisterForm({ ...registerForm, [e.target.name]: e.target.value });
  }

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(loginForm),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Login failed");
      }
    } catch {
      setError("Could not reach the server");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(registerForm),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Registration failed");
      }
    } catch {
      setError("Could not reach the server");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Invoice Reviewer</h1>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Log In
          </button>
          <button
            className={`auth-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Register
          </button>
        </div>

        {mode === "login" && (
          <form className="auth-form" onSubmit={handleLogin}>
            <label>Email
              <input type="email" name="email" value={loginForm.email} onChange={handleLoginChange} required />
            </label>
            <label>Password
              <input type="password" name="password" value={loginForm.password} onChange={handleLoginChange} required />
            </label>
            {error && <p className="auth-error">{error}</p>}
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? "Logging in…" : "Log In"}
            </button>
          </form>
        )}

        {mode === "register" && (
          <form className="auth-form" onSubmit={handleRegister}>
            <label>Store Name
              <input type="text" name="store_name" value={registerForm.store_name} onChange={handleRegisterChange} required />
            </label>
            <label>Email
              <input type="email" name="email" value={registerForm.email} onChange={handleRegisterChange} required />
            </label>
            <label>Password
              <input type="password" name="password" value={registerForm.password} onChange={handleRegisterChange} required />
            </label>
            {error && <p className="auth-error">{error}</p>}
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? "Registering…" : "Register"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
