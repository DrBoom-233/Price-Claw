# Price Claw

Price Claw is a local desktop app for extracting product names, prices, and related structured data from e-commerce `.mhtml` pages. It combines an Electron desktop shell, a React/Vite frontend, and a FastAPI backend that drives browser automation, OCR, schema generation, reusable extraction schemas, and MongoDB-backed result inspection.

The app is designed for local use: you bring your own LLM API key, upload saved `.mhtml` pages, review or reuse extraction schemas, and export extracted price JSON or schemas from the UI.

## Features

- Desktop app powered by Electron, React, Vite, and FastAPI.
- Upload one or more `.mhtml` product/listing pages.
- Configure LLM provider and API key from the frontend.
- Supported providers: OpenAI, Claude, Gemini, DeepSeek, and OpenAI-compatible endpoints.
- Generate extraction schemas with LLM assistance when needed.
- Reuse saved schemas for repeat extraction on the same site/domain.
- Store schemas, extraction tasks, and extraction results in MongoDB.
- Inspect MongoDB price results and schemas from the app.
- Export selected price JSON and selected schema JSON.
- Save local output files under `price_info_output/`.

## Architecture

```text
Price_Claw/
|-- client.py                 # FastAPI app, API routes, websocket pipeline entry
|-- server.py                 # Thin uvicorn launcher
|-- pipeline_service.py       # OCR, schema building, and extraction orchestration
|-- llm_client.py             # LLM provider abstraction
|-- app_settings.py           # Local runtime settings and masked API key view
|-- db.py                     # MongoDB connection and index setup
|-- repositories.py           # MongoDB repositories for schemas/tasks/extractions
|-- electron/                 # Electron main and preload scripts
|-- frontend/                 # React + Vite frontend
|-- mhtml_output/             # Uploaded .mhtml files, generated locally
|-- price_info_output/        # Extracted JSON output files, generated locally
|-- public/                   # Runtime assets/screenshots, generated locally
`-- extraction_schemas/       # Local schema artifacts, generated locally
```

Runtime flow:

1. Electron starts or waits for the FastAPI backend.
2. The React frontend talks to FastAPI through `/api/*` and `/api/ws`.
3. FastAPI launches Playwright Chromium for page/screenshot work.
4. The pipeline uses OCR and LLM calls to build or apply extraction schemas.
5. Results are written to MongoDB and local JSON output directories.

## Prerequisites

Install these before running the project:

- Python 3.12 or newer
- Node.js 20 or newer
- npm
- [uv](https://github.com/astral-sh/uv)
- MongoDB 6 or newer, running locally or reachable by URI
- Tesseract OCR
- Playwright Chromium browser binaries

Recommended versions used during development:

- Python: 3.12+
- Node.js: 20+
- Electron: 35.x
- Vite: 6.x
- FastAPI: 0.128+
- Playwright: 1.52+

### Install uv

Follow the official uv installation guide:

```bash
https://github.com/astral-sh/uv
```

After installing, verify:

```bash
uv --version
```

### Install MongoDB

For local development, start MongoDB on the default URI:

```bash
mongodb://127.0.0.1:27017
```

The app uses database name `price_claw` by default. You can override this with environment variables later.

### Install Tesseract OCR

Install Tesseract and make sure the binary is available to Python. If it is not on `PATH`, set:

```bash
TESSERACT_CMD=/absolute/path/to/tesseract
```

On Windows this often looks like:

```powershell
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## Installation

Clone the repository:

```bash
git clone https://github.com/<your-org-or-user>/Price_Claw.git
cd Price_Claw
```

Create and sync the Python environment:

```bash
uv venv
uv sync
```

Install Playwright Chromium:

```bash
uv run playwright install chromium
```

Install root Electron/dev dependencies:

```bash
npm install
```

Install frontend dependencies:

```bash
npm --prefix frontend install
```

## Configuration

Most users should configure the LLM provider from the app's Settings dialog after startup. The backend stores the local settings in:

```text
.app_settings.json
```

This file is intentionally gitignored because it contains your API key.

### LLM settings from the UI

Open Settings in the desktop app and provide:

- Provider: `openai`, `claude`, `gemini`, `deepseek`, or `openai_compatible`
- API key
- Base URL, if the provider needs one
- Model
- Reasoning model, if different from the main model

When settings are read back by the frontend, the API key is masked.

### LLM settings from environment variables

You can also configure the backend with environment variables. These are useful for backend-only runs or automation:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=your_api_key
LLM_MODEL=gpt-4o-mini
LLM_REASONING_MODEL=o4-mini
LLM_BASE_URL=
```

Provider-specific fallback variables are also supported:

```bash
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_REASONING_MODEL=o4-mini

ANTHROPIC_API_KEY=your_anthropic_key

GEMINI_API_KEY=your_gemini_key
GOOGLE_API_KEY=your_google_key

DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_CHAT_MODEL=deepseek-chat
DEEPSEEK_REASONING_MODEL=deepseek-reasoner
DEEPSEEK_URL=https://api.deepseek.com
```

### MongoDB settings

By default:

```bash
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=price_claw
```

Override them when needed:

```bash
MONGODB_URI=mongodb://user:password@host:27017
MONGODB_DB_NAME=price_claw
```

MongoDB is required for schema listing, schema reuse, extraction history, and the MongoDB Inspector UI.

### Electron/backend settings

Electron supports these optional environment variables:

```bash
BACKEND_BASE_URL=http://127.0.0.1:8000
BACKEND_COMMAND=uv
BACKEND_ARGS="run python server.py"
ELECTRON_START_URL=http://127.0.0.1:5173
ELECTRON_SKIP_BACKEND=1
ELECTRON_OPEN_DEVTOOLS=1
```

Use `ELECTRON_SKIP_BACKEND=1` only when you already started the backend yourself.

## Running the App

### All-in-one development mode

Start backend, Vite frontend, and Electron together:

```bash
npm run dev
```

This starts:

- FastAPI backend at `http://127.0.0.1:8000`
- Vite frontend at `http://127.0.0.1:5173`
- Electron desktop window loading the Vite frontend

Stop the stack with `Ctrl+C` in the terminal, or close the Electron window.

### Backend only

```bash
uv run python server.py
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"ok": true}
```

### Frontend only

In another terminal, with the backend already running:

```bash
npm run dev:frontend
```

The frontend proxies `/api` to `http://127.0.0.1:8000`.

### Electron only

Build the frontend first:

```bash
npm run build:frontend
```

Then start Electron:

```bash
npm run start:electron
```

If the backend is not already running, Electron will try to launch it with `uv run python server.py`.

## Usage Guide

### 1. Save an e-commerce page as `.mhtml`

In your browser, save the target page as a single-file web archive:

- Chrome/Edge: `Save page as...`
- Choose `Webpage, Single File`
- The file should end with `.mhtml`

Price Claw currently accepts `.mhtml` uploads only.

### 2. Start Price Claw

```bash
npm run dev
```

Wait for the Electron window to open.

### 3. Configure LLM settings

Open Settings and save your provider/API key/model settings. This must be done before running a new extraction.

For OpenAI-compatible providers, enter the compatible API base URL and model name expected by that provider.

### 4. Upload `.mhtml` files

Use the upload control in the main UI. The backend stores uploaded files in:

```text
mhtml_output/
```

### 5. Choose extraction mode

Use the UI to decide whether to:

- Generate a new extraction schema with LLM assistance.
- Reuse a saved schema from MongoDB.
- Apply one schema to all uploaded files.
- Configure file-specific extraction plans.

For repeat work on the same site, schema reuse is usually faster and cheaper than generating a new schema.

### 6. Run extraction

Start the task from the UI. Progress logs stream over the websocket endpoint:

```text
/api/ws
```

The backend will:

1. Read the uploaded `.mhtml`.
2. Capture browser-rendered screenshots with Playwright.
3. Run OCR and locate candidate product/price regions.
4. Build or load selectors.
5. Extract structured price data.
6. Save results locally and to MongoDB when available.

### 7. Inspect and export results

Open the MongoDB Data / Inspector view in the app.

You can inspect:

- Recent extraction result JSON
- Saved extraction schemas

Export actions are shown in the selected detail view, so the UI makes clear which price result or schema will be downloaded.

## Output and Local Data

Generated local paths:

```text
.app_settings.json      # Local provider/API key settings, gitignored
mhtml_output/           # Uploaded .mhtml files
price_info_output/      # Extracted price JSON files
public/                 # Runtime screenshots/assets
extraction_schemas/     # Local schema artifacts
.tmp_schemas/           # Temporary materialized schemas
```

MongoDB collections:

```text
schemas       # Saved extraction schemas
extractions   # Extraction results
tasks         # Task status/history
```

These runtime paths are ignored by git by default.

## API Reference

The FastAPI backend exposes these primary routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend health check |
| `GET` | `/api/settings` | Read public/masked runtime settings |
| `POST` | `/api/settings` | Save provider/API key/model settings |
| `POST` | `/api/models` | Fetch or suggest models for a provider |
| `POST` | `/api/upload` | Upload one or more `.mhtml` files |
| `GET` | `/api/schemas` | List saved schemas from MongoDB |
| `GET` | `/api/schemas/{schema_id}` | Read one saved schema |
| `PUT` | `/api/schemas/{schema_id}` | Update schema metadata/config |
| `POST` | `/api/schemas/{schema_id}/clone` | Clone a schema |
| `DELETE` | `/api/schemas/{schema_id}` | Archive a schema |
| `GET` | `/api/inspection` | Read recent extractions and schemas |
| `WS` | `/api/ws` | Run extraction and stream logs |

Interactive API docs are available while the backend is running:

```text
http://127.0.0.1:8000/docs
```

## Useful Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start backend, frontend, and Electron together |
| `npm run dev:backend` | Start only FastAPI backend |
| `npm run dev:frontend` | Start only Vite frontend |
| `npm run dev:electron` | Start Electron against the Vite frontend |
| `npm run build:frontend` | Build React frontend |
| `npm run start:electron` | Start Electron against built frontend |
| `uv run python server.py` | Start backend directly |
| `uv run playwright install chromium` | Install Playwright Chromium |

## Troubleshooting

### `uv` is not recognized

Install uv and restart your terminal. If you are on Windows and have a local virtual environment from a previous setup, you may be able to run:

```powershell
.\.venv\Scripts\uv.exe run python server.py
```

### Backend health check fails

Check that:

- Port `8000` is free.
- Python dependencies were installed with `uv sync`.
- Playwright Chromium was installed with `uv run playwright install chromium`.
- MongoDB connection errors are not preventing schema-dependent features.

### MongoDB Inspector says MongoDB is unavailable

Start MongoDB and verify:

```bash
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=price_claw
```

Then restart the backend.

### Settings are saved but extraction still fails

Check:

- Provider name is supported.
- API key is valid.
- Base URL matches the provider.
- Model name exists for that provider.
- The machine has network access to the LLM provider.

### Upload fails

Only `.mhtml` files are accepted. Re-save the page as a single-file web archive and try again.

### Tesseract is not found

Install Tesseract and set `TESSERACT_CMD` to the executable path.

### Electron opens but the UI cannot reach the backend

Check that:

- `http://127.0.0.1:8000/api/health` returns `{"ok": true}`.
- `BACKEND_BASE_URL` points to the same backend URL.
- The Vite dev server is running on `http://127.0.0.1:5173` when using `npm run dev:electron`.

## Development Notes

- Keep secrets out of git. `.env` and `.app_settings.json` are ignored.
- Runtime output directories are ignored and can be deleted between runs.
- The backend tolerates missing MongoDB at startup, but schema reuse, schema listing, and inspection features require MongoDB.
- For frontend changes, run `npm run build:frontend` before launching the built Electron app.
- For backend changes, restart `uv run python server.py` or `npm run dev`.

## Contributing

Issues and pull requests are welcome. For useful bug reports, include:

- Operating system
- Python, Node.js, and uv versions
- Whether MongoDB is local or remote
- LLM provider and model name, without API keys
- Reproduction steps
- Relevant backend/frontend logs

Before opening a pull request, verify the app starts locally:

```bash
uv sync
uv run playwright install chromium
npm install
npm --prefix frontend install
npm run build:frontend
```

## License

Add your preferred open-source license before publishing the repository.
