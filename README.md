# Quote Recovery Bot

Automatically follows up with prospects who received a quote but haven't responded. Built with Flask, Twilio, and Claude AI.

## How it works

1. Zapier/Housecall Pro sends quote data to `POST /webhook`
2. The bot saves the quote and starts a 48-hour timer
3. After 48 hours, Claude writes a personalized follow-up SMS and Twilio sends it
4. When the prospect replies, the contractor gets an instant alert SMS

## Setup

### 1. Clone and install dependencies

```bash
cd quote_recovery_bot
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in all values:

| Variable | Where to find it |
|---|---|
| `TWILIO_ACCOUNT_SID` | [console.twilio.com](https://console.twilio.com) |
| `TWILIO_AUTH_TOKEN` | [console.twilio.com](https://console.twilio.com) |
| `TWILIO_FROM_NUMBER` | Your Twilio phone number in E.164 format (`+1...`) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `DATABASE_PATH` | Leave as `quotes.db` unless you need a custom path |
| `PORT` | Leave as `5000` |
| `FOLLOW_UP_HOURS` | Default `48` — adjust if needed |

### 3. Run the server

```bash
python quote_recovery_app.py
```

The server starts on `http://0.0.0.0:5000`. You'll see scheduler activity in the console.

### 4. Expose to the internet (for Twilio + Zapier)

Use [ngrok](https://ngrok.com) for local testing:

```bash
ngrok http 5000
```

Copy the `https://` URL ngrok gives you.

## Configuring Twilio

1. Go to your Twilio phone number settings
2. Under **Messaging → A message comes in**, set:
   - Webhook URL: `https://your-ngrok-url.ngrok.io/inbound`
   - Method: `HTTP POST`

## Configuring Zapier

Create a Zap: **Housecall Pro → Webhook**

- Trigger: New quote created in Housecall Pro
- Action: POST to `https://your-url/webhook`
- Body (JSON):

```json
{
  "quote_id":         "{{quote_id}}",
  "prospect_name":    "{{customer_name}}",
  "prospect_phone":   "{{customer_phone}}",
  "contractor_name":  "{{company_name}}",
  "contractor_phone": "{{company_phone}}",
  "quote_amount":     "{{quote_total}}",
  "job_type":         "{{job_type}}"
}
```

## Testing

Send a test quote to the local server:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "quote_id":         "test-001",
    "prospect_name":    "Sarah Johnson",
    "prospect_phone":   "+15862377667",
    "contractor_name":  "Mike'\''s Heating",
    "contractor_phone": "+15551234567",
    "quote_amount":     "$350",
    "job_type":         "HVAC tune-up"
  }'
```

With the scheduler in 2-minute test mode, the follow-up SMS will fire on the next hourly tick after 2 minutes have passed.

## API Reference

### `POST /webhook`
Receives a new quote. Returns `{"status": "received", "quote_id": "..."}`.

**Required fields:** `quote_id`, `prospect_name`, `prospect_phone`, `contractor_name`, `contractor_phone`, `quote_amount`, `job_type`

### `POST /inbound`
Twilio calls this when a prospect replies. Logs the reply and notifies the contractor.

### `GET /health`
Returns `{"status": "ok"}` — use for uptime monitoring.

## Quote status lifecycle

```
pending → followed_up → closed / cancelled
```

- `pending` — quote received, waiting for 48h window
- `followed_up` — follow-up SMS sent
- `closed` / `cancelled` — set manually or via future integration

## Project structure

```
quote_recovery_bot/
├── quote_recovery_app.py       # Flask server + webhooks
├── quote_database.py           # SQLite CRUD operations
├── follow_up_scheduler.py      # APScheduler 48-hour timer logic
├── twilio_sms.py               # Twilio send/receive helpers
├── claude_message_generator.py # Claude API message generation
├── requirements.txt
├── .env.example
└── README.md
```
