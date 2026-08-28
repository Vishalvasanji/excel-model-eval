# LIHTC screening connector

A remote MCP server that runs the acquisition/rehab underwriting model. It
imports `lihtc_screen` directly, so the connector, the CLI and the test suite
all run the same engine against the same reference data.

## Deploy

From this directory:

```bash
npx vercel deploy --prod
```

The repository root is included in the deployment, since the function imports
`lihtc_screen` from it.

Set the shared token before the first request:

```bash
npx vercel env add SCREEN_API_TOKEN production
```

Use a long random value, e.g. `openssl rand -hex 32`. **Without
`SCREEN_API_TOKEN` set, the server refuses every request** rather than running
open — a missing token is treated as a closed door, not an absent lock.

## Add it to Claude

Settings → Connectors → Add custom connector:

- **URL** — the deployment URL Vercel prints
- **Authentication** — Bearer token, the value of `SCREEN_API_TOKEN`

Check it is alive first (this endpoint needs no token and returns no deal data):

```bash
curl https://<your-deployment>/health
```

## Tools

| Tool | What it answers |
|---|---|
| `screen_deal` | The whole screen: verdict, minimum soft funding, maximum supportable price, sources and uses, and every failing QAP rule with its citation |
| `solve_max_price` | The most that can be paid at a given level of subsidy, and the price supported across a range of subsidy levels |
| `sensitivity` | How the answer moves across a range of one input |
| `get_defaults` | What the screen would assume for a property of this size and location, before running it |
| `list_markets` | Markets with bundled rent limits and utility allowances, and the source of each |

## Run it locally

```bash
SCREEN_API_TOKEN=dev python mcp_server/api/index.py

curl -s localhost:8000 -H 'Authorization: Bearer dev' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m json.tool
```

## Notes

- The engine is pure standard library; `requirements.txt` is empty by design.
- A screen takes well under a second, so the 60s function timeout is slack, not
  a constraint.
- Reference data is bundled, so a deployment is self-contained: no database, no
  outbound calls at request time.
