# AI Vacation Planner

A REST API for planning vacations. Users register, create trips, and attach day-by-day itineraries to each trip. All trip and itinerary data is private to the authenticated user.

Built with **FastAPI**, **SQLAlchemy**, **SQLite**, and **JWT authentication**.

## Architecture

```
ai-vacation-planner/
└── ai-vacation-planner-backend/
    ├── .env                        # Environment variables (not committed)
    ├── pyproject.toml              # Dependencies and build config
    └── src/
        └── app/
            ├── main.py             # App entry point, router registration
            ├── config.py           # Settings loaded from .env
            ├── database.py         # SQLAlchemy engine and session
            ├── models/             # ORM table definitions
            │   ├── user.py         # User table
            │   ├── trip.py         # Trip table (FK → User)
            │   └── itinerary.py    # Itinerary table (FK → Trip)
            ├── schemas/            # Pydantic request/response schemas
            │   ├── auth.py
            │   ├── trip.py
            │   └── itinerary.py
            ├── routers/            # Route handlers grouped by resource
            │   ├── auth.py         # /auth and /users
            │   ├── trips.py        # /trips
            │   └── itineraries.py  # /itineraries
            ├── dependencies/
            │   └── auth.py         # get_current_user dependency
            └── utils/
                └── security.py     # Password hashing and JWT helpers
```

**Data model:**
- A `User` has many `Trip`s.
- A `Trip` has one `Itinerary`.
- An `Itinerary` stores all days as a JSON array (each day has a number and a list of activities).
- Deleting a `User` cascades to their `Trip`s; deleting a `Trip` cascades to its `Itinerary`.


## LLM Integration

**Model:** Anthropic Claude (`claude-haiku-4-5`)
**Trigger:** `POST /itineraries/` with `generate_with_ai: true`

**Flow:**
1. Route handler fetches the trip from the database
2. Trip details (`destination`, `days`, `budget`, `trip_style`) are passed to `llm_service.generate_itinerary()`
3. A system prompt establishes Claude as an expert travel planner with rules for geographic accuracy, budget respect, and JSON-only responses
4. A user prompt is built with the trip details, activity count requirements (3–5 per day), and mix rules (sightseeing, food, local culture)
5. Claude responds with a structured JSON object
6. The response is validated, parsed, saved to the database, and returned to the client

**Error handling:**
- If the LLM returns invalid JSON → 500: `"LLM returned invalid JSON format"`
- If the response is missing the `days` key → 500: `"LLM response missing required itinerary structure"`
- If the Anthropic API call fails → 500 with the error detail


## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)


## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd ai-vacation-planner/ai-vacation-planner-backend
```

### 2. Install dependencies

```bash
poetry install
```

### 3. Create the `.env` file

```bash
cp .env.example .env   # if available, or create it manually
```

The `.env` file must contain at minimum:

```env
SECRET_KEY=your-secret-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

The app will **refuse to start** if `SECRET_KEY` or `ANTHROPIC_API_KEY` is missing because they are configured to be required fields.

### 4. Run the server

```bash
poetry run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.


## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | Secret used to sign JWT tokens. Must be at least 32 characters. |
| `DATABASE_URL` | No | `sqlite:///./ai_vacation_planner.db` | SQLAlchemy database URL |
| `ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_IN` | No | `30` | Token expiry in minutes |
| `DEBUG` | No | `True` | Enables SQLAlchemy query logging |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key for AI itinerary generation. Get it from https://console.anthropic.com |


## API Endpoints

Interactive docs are available at **`/docs`** (Swagger UI) or **`/redoc`** once the server is running.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | No | Create a new user account |
| `POST` | `/auth/login` | No | Log in and receive a JWT token |
| `GET` | `/users/me` | Yes | Get the authenticated user's profile |

Your can use GUI documentation of Swagger, Postman or use Terminal command below....

**Register**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "username": "myuser", "password": "mypassword"}'
```

**Login**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "mypassword"}'
```

The response contains an `access_token`. Pass it as a `Bearer` token in the `Authorization` header for all protected routes:

```
Authorization: Bearer <access_token>
```

### Trips

All trip endpoints require authentication. Users can only access their own trips.

| Method | Path | Description |
|---|---|---|
| `POST` | `/trips/` | Create a new trip |
| `GET` | `/trips/` | List all trips for the current user |
| `GET` | `/trips/{trip_id}` | Get a single trip by ID |
| `PUT` | `/trips/{trip_id}` | Update trip details |
| `DELETE` | `/trips/{trip_id}` | Delete a trip (also deletes its itinerary) |

**Create a trip**
```bash
curl -X POST http://localhost:8000/trips/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"destination": "Paris", "days": 5, "budget": 1500.0, "trip_style": "budget"}'
```

**Allowed `trip_style` values:** `budget`, `luxury`, `family`, `adventure`, `romantic`, `business`

### Itineraries

| Method | Path | Description |
|---|---|---|
| `POST` | `/itineraries/` | Create an itinerary for a trip |
| `GET` | `/itineraries/{trip_id}` | Get the itinerary for a trip |

Each trip can have only one itinerary. The itinerary is made up of days, each with a list of activities.

**Create an itinerary**
```bash
curl -X POST http://localhost:8000/itineraries/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": 1,
    "days": [
      {"day": 1, "activities": ["Eiffel Tower", "Seine River Walk"]},
      {"day": 2, "activities": ["Louvre Museum", "Montmartre"]}
    ]
  }'
```

### AI Itinerary Generation

**How it works**
- `POST /itineraries/` accepts an optional `generate_with_ai` boolean field (default: `false`)
- When `generate_with_ai` is `true`, the backend reads the trip details from the database, builds a prompt using destination, days, budget, and trip_style, and calls Claude (`claude-haiku-4-5`) to generate a realistic day-by-day itinerary
- The generated itinerary is saved to the database and returned in the same format as a manually created one

**Modes**

Manual mode — provide the days array yourself:
```json
{
  "trip_id": 1,
  "generate_with_ai": false,
  "days": [
    {"day": 1, "activities": ["Eiffel Tower", "Seine River Walk"]},
    {"day": 2, "activities": ["Louvre Museum", "Montmartre"]}
  ]
}
```

AI mode — let Claude generate the itinerary:
```json
{
  "trip_id": 1,
  "generate_with_ai": true
}
```

**Requirements for AI mode**
- `ANTHROPIC_API_KEY` must be set in `.env`
- The trip must already exist (create it first via `POST /trips/`)
- The generated itinerary contains 3–5 real activities per day, respecting the trip budget and style

---

## Status Codes

| Code | Meaning |
|---|---|
| `200` | OK |
| `201` | Resource created |
| `400` | Bad request (e.g. duplicate email, itinerary already exists) |
| `401` | Invalid or expired token |
| `403` | Missing token |
| `404` | Resource not found |
| `422` | Validation error (e.g. invalid `trip_style`, missing required field) |
