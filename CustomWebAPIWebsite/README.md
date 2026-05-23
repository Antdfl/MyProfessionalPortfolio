# Custom Web API Website — Barcode Product Scanner

A Flask web application that scans a barcode from an uploaded image and returns product information in three languages (English, Italian, Spanish).

## Overview

The user uploads a photo of a barcode (JPG or PNG). The app reads the barcode value from the image, looks up the product in an open food database, translates the result into the selected language, and displays the product details on the same page.

The pipeline runs three external APIs in sequence:

1. **Cloudmersive Barcode API** — extracts the barcode value from the image
2. **Open Food Facts API** — retrieves product name, brand, category, and quantity from the barcode
3. **Google Translate (via deep-translator)** — translates the product name and category into the selected language

## Technical Stack

- **Python 3.10+**
- `flask` — web framework and routing
- `cloudmersive-barcode-api-client` — barcode image recognition
- `requests` — HTTP calls to Open Food Facts
- `deep-translator` — Google Translate wrapper for product field translation
- `python-dotenv` — API key management via `.env`
- Standard library: `os`, `tempfile`, `pathlib`

## Project Structure

```text
CustomWebAPIWebsite/
├── app.py              # Flask application — routes, API calls, translation logic
├── main.py             # Standalone CLI script used during development and testing
├── .env                # API keys (not committed)
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Single template: upload form + result table
└── static/
    └── style.css       # Page styling and language switcher
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```ini
API_KEYS=your_cloudmersive_api_key
```

Run the development server:

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## How It Works

### Step 1 — Barcode scan (Cloudmersive)

The uploaded image is saved to a temporary file and passed to `BarcodeScanApi.barcode_scan_image()`. The SDK sends the file as `multipart/form-data` to the Cloudmersive endpoint, which returns the barcode value and type (e.g. `EAN_13`, `UPC_A`). The temporary file is deleted immediately after the call regardless of outcome.

Supported barcode types include EAN-8, EAN-13, UPC-A, UPC-E, QR Code, Code 128, and others.

**Image quality note:** the standard scan endpoint performs well on sharp, well-lit images. Blurry or low-contrast photos reliably return HTTP 500 from the Cloudmersive server rather than a graceful error. For production use with unreliable image sources, `barcode_scan_image_advanced` (AI-enhanced, 100 API calls/image) would be the appropriate endpoint.

### Step 2 — Product lookup (Open Food Facts)

The barcode value is sent to the Open Food Facts REST API:

```text
GET https://world.openfoodfacts.org/api/v2/product/{barcode}.json
```

If `status == 1`, the product was found and the following fields are extracted: `product_name`, `brands`, `categories`, `quantity`.

**Database coverage:** Open Food Facts is community-driven and covers food and beverage products globally. Non-food items (cleaning products, electronics, etc.) and many regional products from specific countries are typically absent. The API returns `status: 0` for missing entries, which the app handles with a user-facing error message.

### Step 3 — Translation (Google Translate)

`product_name` and `categories` are translated into the selected language using `GoogleTranslator(source='auto', target=lang)`. The `source='auto'` setting handles the fact that Open Food Facts stores data in the contributor's language, which varies by product (commonly French, English, or Italian). Brand names are not translated as they are proper nouns.

### Internationalisation

The UI supports three languages: **English** (default), **Italian**, and **Spanish**.

Language selection is handled via a query parameter (`?lang=en`). A hidden `<input>` field in the upload form carries the active language through the POST request to `/scan`, so the result page renders in the same language without a redirect.

All UI strings (labels, button text, error messages, and the disclaimer) are stored in a `TRANSLATIONS` dict in `app.py` keyed by language code. No database or external i18n library is required.

```python
TRANSLATIONS = {
    'en': { 'title': 'Barcode Scanner', 'scan_button': 'Scan', 'home_button': 'Home', 'disclaimer': '...', ... },
    'it': { 'title': 'Barcode Scanner', 'scan_button': 'Scansiona', 'home_button': 'Home', 'disclaimer': '...', ... },
    'es': { 'title': 'Escáner de Códigos de Barras', 'scan_button': 'Escanear', 'home_button': 'Inicio', 'disclaimer': '...', ... },
}
```

### Language Switcher Lock

Once the user selects a file, the EN / IT / ES switcher buttons are disabled so the language cannot be changed mid-upload. The lock is applied at two levels:

- **Client-side (immediate):** a JavaScript `change` listener on the file input adds a `lang-locked` CSS class to the switcher as soon as a file is chosen. The class sets `pointer-events: none` on the links, blocking any click before the form is submitted.
- **Server-side (after POST):** when `/scan` renders a response (result or error), the template replaces the `<a>` links with non-interactive `<span>` elements, making the lock structural rather than style-only.

### Navigation and Disclaimer

**Home button:** a "Home" link styled as a secondary button appears at the bottom of the page only after a scan has been attempted (success or error). It returns the user to `/?lang=<current>`, preserving the active language. The button is absent on the initial upload page to keep the interface uncluttered.

**Disclaimer:** a short notice is displayed at the bottom of the home page (upload form state only) in the active language:

- **EN:** *"This is a demo portfolio site. Product search is limited to food items only."*
- **IT:** *"Questo è un sito portfolio dimostrativo. La ricerca di prodotti è limitata solo a prodotti alimentari."*
- **ES:** *"Este es un sitio de portafolio de demostración. La búsqueda de productos está limitada solo a productos alimenticios."*

The disclaimer is hidden after a scan to avoid visual clutter on the result page.

### Routes

| Method | Route   | Description                                              |
|--------|---------|----------------------------------------------------------|
| GET    | `/`     | Renders the upload form                                  |
| POST   | `/scan` | Processes the image, calls both APIs, renders the result |

### Error Handling

| Condition                        | User-facing message (varies by language)              |
|----------------------------------|-------------------------------------------------------|
| No file submitted                | "No file selected."                                   |
| Unsupported file format          | "Unsupported format. Use JPG or PNG."                 |
| Cloudmersive API error           | "Scan error. Please try again."                       |
| Barcode not readable in image    | "Barcode not recognized. Try with a sharper image."   |
| Product not found in database    | "Product with code {barcode} not found in database."  |

## API Keys and Limits

| API              | Plan                       | Limit              | Key required |
|------------------|----------------------------|--------------------|--------------|
| Cloudmersive     | Free tier                  | 800 calls/month    | Yes          |
| Open Food Facts  | Open/free                  | No limit           | No           |
| Google Translate | Free (via deep-translator) | Unofficial, no key | No           |

## Development Notes

`main.py` was written first as a standalone script to validate each API call in isolation before integrating them into Flask. It remains in the repository as a reference and quick-test tool. The logic in `app.py` is a direct port of `main.py` adapted for HTTP request/response handling.
