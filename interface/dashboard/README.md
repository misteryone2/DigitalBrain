# DigitalBrain Dashboard (static, read-only)

Static observability dashboard for DigitalBrain. It consumes only authenticated read-only API endpoints (`/v1/*`) on demand.

## Guarantees
- **Read-only**: no mutation endpoints, no write actions.
- **No mock runtime state**: cards render API responses or explicit load/auth/config errors.
- **On-demand snapshot**: data loads only when the user clicks "Load snapshot".

## Endpoints used
- `GET /v1/health`
- `GET /v1/plans?limit=10`
- `GET /v1/outcomes?limit=10`
- `GET /v1/promotions?limit=10`
- `GET /v1/audit?limit=10`

## Usage
1. Start API with required env vars:
   - `DIGITALBRAIN_API_TOKEN`
   - `DIGITALBRAIN_API_SCOPES` (optional, default `read:*`)
   - configured DB env vars for the stores you want exposed
2. Serve `interface/dashboard/` with a static file server, or open `index.html` directly.
3. Enter API base URL and bearer token, then load snapshot.

## CORS note
If loading from a different origin, the API must allow browser CORS for the dashboard origin. The stdlib API is minimal and may need a reverse proxy/static serving strategy in local setups.
