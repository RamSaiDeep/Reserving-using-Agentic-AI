# Reserving using Agentic AI

An AI-assisted actuarial reserving webapp for uploading loss development data, reviewing triangle diagnostics, selecting reserving methods, calculating IBNR, and asking an agentic assistant questions about the results.

The app is intentionally split into:

- **Dashboard frontend**: static HTML/CSS/JavaScript in `dashboard/`.
- **FastAPI backend**: API entrypoint in `app/backend/main.py`, with compatibility import from `backend/main.py`.
- **Domain reserving code**: triangle parsing and reserving methods in `backend/models/`, exposed through the newer `src/` service and agent layers.
- **Agent orchestration**: supervisor-agent pattern in `src/agents/` so future agents can be added without rewriting existing agents.

## What you can do in the webapp

1. Upload a CSV loss triangle or long-format actuarial dataset.
2. Let the backend detect the data shape and build a loss development triangle.
3. Review accident years, development periods, total paid, premium availability, and completeness.
4. Inspect and edit selected loss development factors.
5. Compare recommended reserving methods.
6. Run a reserving method and view IBNR / ultimate loss estimates.
7. Optionally connect a Gemini API key for AI-generated explanations and chat.

## Supported reserving methods

The backend currently supports these methods:

| Code | Method |
| --- | --- |
| `CL` | Chain Ladder |
| `MCL` | Mack Chain Ladder |
| `BF` | Bornhuetter-Ferguson |
| `BK` | Benktander |
| `CC` | Cape Cod |
| `CO` | Case Outstanding |
| `CLK` | Clark Stochastic approximation |

## Prerequisites

Install these before running the app locally:

- Python 3.10+
- A modern browser
- Optional: a Gemini API key if you want AI narrations and chat

## Setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If you are on Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Start the backend

Run the FastAPI server from the repository root:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at:

- API base URL: `http://localhost:8000/api`
- OpenAPI docs: `http://localhost:8000/docs`

## Start the dashboard

In a second terminal, serve the static dashboard:

```bash
cd dashboard
python -m http.server 3000
```

Then open this URL in your browser:

```text
http://localhost:3000
```

The dashboard JavaScript calls the backend at `http://localhost:8000/api`, so keep both terminals running.

## Walk through the webapp

### 1. Confirm both servers are running

Before uploading data:

- Backend terminal should show Uvicorn running on port `8000`.
- Frontend terminal should show the static file server running on port `3000`.
- Browser should show the Actuarial Reserve dashboard.

### 2. Optional: add your Gemini API key

Click **Gemini API Key** in the top-right corner and paste your key.

This is optional. Without a key, the backend can still parse data, build triangles, recommend methods, and calculate reserves. With a key, the app also provides AI narrations and chat responses.

### 3. Upload a CSV file

Use the upload panel to drag and drop a CSV, or click the upload area and select one.

You can try one of the included files:

- `dashboard/sample_auto_liability.csv`
- `dashboard/comauto_pos.csv`
- `data/comauto_pos.csv`

The backend supports both:

- **Wide triangle format**, where accident years are rows and development ages are columns.
- **Long format**, where rows contain accident year, development lag, paid/incurred loss, premium, counts, or exposure fields.

### 4. Review the data summary

After upload, the app shows a summary including:

- Number of accident years
- Number of development periods
- Latest diagonal total paid
- Whether premium data is available
- Triangle completeness
- Whether the data appears immature or long-tailed

If Gemini is connected, the agent activity panel will also explain what it found.

### 5. Generate and inspect the loss triangle

Click **Generate Loss Triangle**.

On this screen, review:

- The cumulative paid loss triangle
- Volume-weighted LDFs
- Straight-average LDFs
- 3-year and 5-year weighted averages
- Selected LDFs used for projections

You can edit selected LDFs directly before running a model.

### 6. Continue to method selection

After reviewing the triangle and LDF selections, continue to the model selection step.

The recommendation engine ranks methods based on dataset characteristics, including:

- Premium availability
- Triangle completeness
- New-line or immature data indicators
- Long-tail development indicators

### 7. Choose a reserving method

Select a method from the ranked list. Some methods may require extra inputs:

- BF / Benktander may need an a priori loss ratio.
- Cape Cod uses premium or exposure-like data where available.
- Chain Ladder and Mack primarily use selected development factors.

### 8. Run the model

Submit the method parameters to calculate results.

The results page shows:

- Paid losses by accident year
- CDF to ultimate
- Percent reported
- Ultimate loss estimate
- IBNR estimate
- Method-specific fields, such as Mack standard error and confidence indications

### 9. Ask questions in the agent chat

Use the chat panel on the left to ask questions such as:

- “Why is the latest accident year IBNR so high?”
- “Which LDF is driving the reserve?”
- “Why did the app recommend BF over Chain Ladder?”
- “What does the Mack standard error mean?”

Chat requires a Gemini API key. The chat receives the current app context, including uploaded data, selected LDFs, method selection, and results.

## Troubleshooting

### The dashboard says the backend failed

Check that the backend is running on port `8000`:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Also confirm the browser can reach:

```text
http://localhost:8000/docs
```

### Python cannot import dependencies

Reinstall requirements inside your active virtual environment:

```bash
python -m pip install -r requirements.txt
```

### AI narration does not appear

AI narration is optional. If calculations work but narration does not appear:

- Confirm you saved a Gemini API key in the dashboard.
- Confirm the key is valid.
- Check the backend terminal for Gemini API errors or rate limits.

### The CSV does not parse correctly

Confirm your file includes recognizable columns. Helpful column names include:

- Accident year: `accident_year`, `accidentyear`, `ay`, `origin`, `year`
- Development age: `developmentlag`, `dev`, `dev_age`, `lag`, `age`
- Paid loss: `paid`, `cumpaidloss`, `loss`
- Incurred loss: `incurred`, `reported`
- Premium: `premium`, `earnedprem`, `earnedpremnet`

## Project structure

```text
app/
  api/                 FastAPI route modules
  backend/             FastAPI app factory
  frontend/            Reserved for future React/Next.js frontend
backend/               Compatibility backend modules and existing domain math
src/
  agents/              Supervisor and specialist agents
  reserving/           Reserving method registry and method packages
  services/            Application service layer
  triangles/           Triangle construction and development helpers
dashboard/             Current static browser dashboard
data/                  Sample and source data files
docs/                  Architecture and user documentation
tests/                 Unit, integration, API, and agent tests
```

## Development notes

- Do **not** add a monolithic `app.py`.
- Keep reserving methods independent from agent orchestration.
- Add new agents by registering them with the agent registry.
- Add new reserving methods by registering a `MethodBase` implementation with the reserving registry.
