# Price Claw (Electron + React + FastAPI)

Local desktop extraction app for e-commerce `.mhtml` pages.

## Architecture

- `frontend/`: React + Vite UI.
- `electron/`: desktop shell (main/preload), starts backend process.
- `client.py` / `server.py`: FastAPI backend.

## Prerequisites

- Python 3.12+
- Node.js 20+
- [uv](https://github.com/astral-sh/uv)
- Playwright browser binaries: `uv run playwright install chromium`
- Tesseract OCR (set `TESSERACT_CMD` when needed)

## Install

```bash
uv venv
uv sync
npm install
npm --prefix frontend install
```

## Development (all-in-one)

```bash
npm run dev
```

This starts:

- FastAPI backend on `http://127.0.0.1:8000`
- Vite frontend on `http://localhost:5173`
- Electron desktop window loading the Vite app

## Run backend only

```bash
uv run python server.py
```

Health check:

- `GET http://127.0.0.1:8000/api/health`

## API key settings

- Configure key/model in frontend Settings page.
- Stored locally in `/.app_settings.json` (gitignored).
- Backend only returns masked key in `GET /api/settings`.

## Useful scripts

- `npm run dev:backend`
- `npm run dev:frontend`
- `npm run dev:electron`
- `npm run build:frontend`
- `npm run start:electron`

