# Frontend — Agentic Invoice Reviewer

React 19 + Vite client for the Agentic Invoice Reviewer Flask API. The dev server
proxies `/api` requests to the backend, so the browser only talks to Vite.

## Quick start from a fresh clone

You need the backend running before the frontend. See the
[root README](../README.md) for full backend and SQLite setup.

### 1. Clone the repository

```bash
git clone https://github.com/ebanksfittechdev-cell/Agentic-Invoice-Reviewer.git
cd Agentic-Invoice-Reviewer
git switch arodgers
```

### 2. Start the backend (terminal 1)

```bash
cd backend
python3 -m venv venv              # Windows: py -3 -m venv venv
source venv/bin/activate          # Windows PS: .\venv\Scripts\Activate.ps1
                                  # Windows cmd: venv\Scripts\activate.bat
pip install -r requirements.txt
cp .env.example .env              # Windows: Copy-Item .env.example .env
python init_db.py                 # Windows: py init_db.py
flask run                         # http://127.0.0.1:5000
                                  # Windows: python -m flask run
```

Set `SECRET_KEY` and `GEMINI_API_KEY` in `backend/.env` first. The default
`DATABASE_URL=sqlite:///invoice_reviewer.db` creates
`backend/instance/invoice_reviewer.db` — no database server is required. On
Windows, also set `UPLOAD_FOLDER=C:/invoice_uploads`.

Open that database file with **DB Browser for SQLite** after running
`init_db.py`; see the [root README](../README.md) for details.

### 3. Start the frontend (terminal 2)

```bash
cd frontend
npm install
cp .env.example .env              # Windows: Copy-Item .env.example .env
npm run dev                       # http://localhost:5173
```

Open http://localhost:5173 and log in with `demo@store.com` / `demo1234`.

## Configuration

`frontend/.env` controls the Vite proxy target:

```env
VITE_API_PROXY=http://127.0.0.1:5000
```

Use `127.0.0.1`, not `localhost`: on many systems `localhost` resolves to IPv6
(`::1`) while Flask listens only on IPv4, which causes `ECONNREFUSED`.

After changing `.env`, restart `npm run dev`.

## Running against a backend on another machine

On the backend machine:

```bash
flask run --host=0.0.0.0 --port=5000
# Windows: python -m flask run --host=0.0.0.0 --port=5000

hostname -I                       # Linux: note the LAN IP
# Windows: ipconfig               # use the IPv4 Address

# Linux firewall: sudo ufw allow 5000/tcp
# Windows PowerShell (Administrator):
# New-NetFirewallRule -DisplayName "Flask 5000" -Direction Inbound `
#   -Protocol TCP -LocalPort 5000 -Action Allow
```

On the frontend machine, set `frontend/.env`:

```env
VITE_API_PROXY=http://<backend-lan-ip>:5000
```

Then:

```bash
npm run dev -- --host 0.0.0.0
```

If the browser calls the backend directly (not through the proxy), also add the
frontend origin to `FRONTEND_ORIGINS` in `backend/.env` (comma-separated).

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start the Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run Oxlint |

## Current UI status

Only Login and Register are implemented. A successful login shows
`alert("Logged in as <store name>")`; a successful registration switches back to
the Log In tab with the email pre-filled. There is no router or dashboard yet.

## Project layout

```
frontend/
├── vite.config.js          # /api proxy (VITE_API_PROXY)
├── .env.example
└── src/
    ├── main.jsx
    ├── App.jsx
    └── login page/
        ├── login.jsx       # login + register forms
        └── login.css
```

## Troubleshooting

- **"Connection refused"**: start the backend first and confirm
  `curl http://127.0.0.1:5000/api/auth/me` returns `401`. If it does not, the
  frontend cannot help — fix the backend or the proxy target.
- **Port 5173 already in use**: stop the old Vite process or run
  `npm run dev -- --port 5174`.
- **`localhost:5173` unreachable from another device**: run
  `npm run dev -- --host 0.0.0.0`.
- **CORS errors**: expected only for direct backend calls; use the proxy or add
  the origin to `FRONTEND_ORIGINS` on the backend.
- **Blank page / no HMR**: check the Vite terminal output for compile errors and
  run `npm run lint`.
- **Windows: `'cp' is not recognized`**: use `Copy-Item .env.example .env`.
- **Windows: activation script blocked**: run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use
  `venv\Scripts\activate.bat` from cmd.
- **Windows: other-machine connection fails**: allow port 5000 through Windows
  Firewall and use the `IPv4 Address` from `ipconfig`.
