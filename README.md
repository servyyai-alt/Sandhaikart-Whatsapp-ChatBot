# whatsapp-service

Separate FastAPI bridge service between WhatsApp Cloud API and your existing Sandhaikart dashboard/website.

## Scope and Guardrails

- Existing dashboard remains the single source of truth.
- No admin dashboard UI changes are required here.
- No changes to product management, order management, checkout, login, register, address, payment, or Razorpay logic.
- Products are fetched from existing dashboard APIs only.
- Orders are not finalized in Python; checkout happens in existing website flow.

## Project Structure

```text
whatsapp-service/
  app/
    __init__.py
    main.py
    config.py
    routes/
      __init__.py
      whatsapp_routes.py
      meta_feed_routes.py
      health_routes.py
    services/
      __init__.py
      whatsapp_client.py
      dashboard_client.py
      feed_service.py
      cart_link_service.py
    utils/
      __init__.py
      logger.py
      csv_utils.py
  .env.example
  requirements.txt
  README.md
  run.bat
  run.sh
  .gitignore
```

## Setup

### Windows

```bash
mkdir whatsapp-service
cd whatsapp-service
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn httpx python-dotenv pydantic
pip freeze > requirements.txt
```

### Mac/Linux

```bash
mkdir whatsapp-service
cd whatsapp-service
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn httpx python-dotenv pydantic
pip freeze > requirements.txt
```

## Environment Variables

Create `.env` by copying `.env.example`:

```bash
cp .env.example .env
```

Set:

- `WHATSAPP_TEMP_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `GRAPH_API_VERSION`
- `DASHBOARD_API_BASE`
- `WEBSITE_BASE_URL`
- `DASHBOARD_INTERNAL_API_KEY` (optional)
- `BRAND_NAME`
- `DEFAULT_CURRENCY`

## Run Service

```bash
uvicorn app.main:app --reload --port 8000
```

Or use helper scripts:

- Windows: `run.bat`
- Mac/Linux: `./run.sh`

## Ngrok for Meta Webhook

```bash
ngrok http 8000
```

Use URLs:

- Meta webhook callback URL: `https://your-ngrok-url/webhook/whatsapp`
- Meta product feed URL: `https://your-ngrok-url/meta/product-feed.csv`

## Endpoints

- `GET /` -> health response
- `GET /health` -> health response
- `GET /webhook/whatsapp` -> webhook verification
- `POST /webhook/whatsapp` -> incoming WhatsApp events/messages
- `GET /meta/product-feed.csv` -> Meta Commerce feed CSV

## Webhook Behavior

- `hi`/`hello`/`hey` -> sends welcome + catalog instruction.
- Normal text -> sends instruction to use catalog and send cart.
- Catalog/order payload -> extracts product IDs and quantities, builds checkout bridge URL, sends it to user.

Checkout bridge format:

`{WEBSITE_BASE_URL}/whatsapp-cart?items=PRODUCT_ID:QTY,PRODUCT_ID:QTY`

## Important Frontend Requirement

A minimal customer-side route `/whatsapp-cart` is required to:

1. Read `items` from URL.
2. Add items into existing cart state/localStorage.
3. Redirect customer to existing checkout flow.

This does not change admin dashboard features.

## Product Feed Notes

- Feed is generated from dashboard API in real time.
- Invalid products (missing required fields like id/name/price/image) are skipped and logged.
- Product and order data are not permanently stored in Python service.

## Test Checklist

1. Open `/health`.
2. Verify webhook in Meta.
3. Send `hi` to test WhatsApp number.
4. Open `/meta/product-feed.csv` in browser.
5. Add feed URL in Commerce Manager.
6. Connect catalog to WhatsApp.
7. Select product in WhatsApp catalog.
8. Confirm checkout link message is sent.

## Security

- Never expose WhatsApp token in frontend.
- Never commit `.env`.
- Never hardcode dashboard credentials in code.
- Use environment variables only.
- Temporary token is for development.
- Use permanent/system-user token for production.
