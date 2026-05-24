# =============================================================================
# app.py — Flask web application: barcode scanner + product lookup
#
# Each scan runs three external APIs in sequence:
#   1. Cloudmersive     →  reads the barcode value from the uploaded image
#   2. Open Food Facts  →  fetches product name, brand, category, quantity
#   3. Google Translate →  translates name and category into the user's language
# =============================================================================

import os
import tempfile
import requests
from pathlib import Path
from flask import Flask, render_template, request
from dotenv import load_dotenv
import cloudmersive_barcode_api_client
from cloudmersive_barcode_api_client.rest import ApiException
from deep_translator import GoogleTranslator

# Must be called before any os.getenv() so that variables from .env are
# available when the module-level configuration block runs below.
load_dotenv()

app = Flask(__name__)
# Flask automatically rejects requests that exceed this size with HTTP 413.
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max upload

# -----------------------------------------------------------------------------
# Cloudmersive SDK — initialised once at module level, not per request.
# This reuses the HTTP connection and avoids repeated API client setup overhead.
# -----------------------------------------------------------------------------
configuration = cloudmersive_barcode_api_client.Configuration()
configuration.api_key['Apikey'] = os.getenv('API_KEYS')  # key loaded from .env
scan_api = cloudmersive_barcode_api_client.BarcodeScanApi(
    cloudmersive_barcode_api_client.ApiClient(configuration)
)

# File extensions accepted for upload.
# Validation is done on the filename extension, not the MIME type: acceptable
# for a demo, but insufficient for production (MIME type can be spoofed by the client).
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Language codes supported by the UI.
# To add a new language: add its code here and add the corresponding dict
# in TRANSLATIONS below with every key that exists in the 'en' entry.
SUPPORTED_LANGS = {'en', 'it', 'es'}
DEFAULT_LANG = 'en'

# =============================================================================
# TRANSLATIONS — all UI strings keyed by language code.
# Structure: TRANSLATIONS[lang_code][key] → localised string.
#
# Maintenance notes:
#   - Every language must contain ALL keys present in 'en'.
#     A missing key will raise a KeyError at runtime.
#   - 'error_not_found' contains the {barcode} placeholder, which is filled
#     at runtime via str.format(barcode=...) in the /scan route.
#   - 'na' is the fallback value shown when a product field is missing
#     from the Open Food Facts database.
#   - 'home_button' and 'disclaimer' are the keys added for the Home button
#     and the disclaimer shown at the bottom of the upload page.
# =============================================================================
TRANSLATIONS = {
    'en': {
        'title': 'Barcode Scanner',
        'subtitle': 'Upload a barcode image to get product information.',
        'choose_image': 'Choose an image',
        'scan_button': 'Scan',
        'result_title': 'Result',
        'code_label': 'Code',
        'name_label': 'Name',
        'brand_label': 'Brand',
        'category_label': 'Category',
        'quantity_label': 'Quantity',
        'error_no_file': 'No file selected.',
        'error_format': 'Unsupported format. Use JPG or PNG.',
        'error_scan': 'Scan error. Please try again.',
        'error_no_barcode': 'Barcode not recognized. Try with a sharper image.',
        'error_not_found': 'Product with code {barcode} not found in the database.',
        'na': 'N/A',
        'home_button': 'Home',
        'disclaimer': 'This is a demo portfolio site. Product search is limited to food items only.',
    },
    'it': {
        'title': 'Barcode Scanner',
        'subtitle': "Carica un'immagine di un codice a barre per ottenere le informazioni del prodotto.",
        'choose_image': "Scegli un'immagine",
        'scan_button': 'Scansiona',
        'result_title': 'Risultato',
        'code_label': 'Codice',
        'name_label': 'Nome',
        'brand_label': 'Marca',
        'category_label': 'Categoria',
        'quantity_label': 'Quantità',
        'error_no_file': 'Nessun file selezionato.',
        'error_format': 'Formato non supportato. Usa JPG o PNG.',
        'error_scan': 'Errore durante la scansione. Riprova.',
        'error_no_barcode': "Codice a barre non riconosciuto. Prova con un'immagine più nitida.",
        'error_not_found': 'Prodotto con codice {barcode} non trovato nel database.',
        'na': 'N/D',
        'home_button': 'Home',
        'disclaimer': 'Questo è un sito portfolio dimostrativo. La ricerca di prodotti è limitata solo a prodotti alimentari.',
    },
    'es': {
        'title': 'Escáner de Códigos de Barras',
        'subtitle': 'Sube una imagen de un código de barras para obtener información del producto.',
        'choose_image': 'Elige una imagen',
        'scan_button': 'Escanear',
        'result_title': 'Resultado',
        'code_label': 'Código',
        'name_label': 'Nombre',
        'brand_label': 'Marca',
        'category_label': 'Categoría',
        'quantity_label': 'Cantidad',
        'error_no_file': 'Ningún archivo seleccionado.',
        'error_format': 'Formato no soportado. Usa JPG o PNG.',
        'error_scan': 'Error durante el escaneo. Inténtalo de nuevo.',
        'error_no_barcode': 'Código de barras no reconocido. Prueba con una imagen más nítida.',
        'error_not_found': 'Producto con código {barcode} no encontrado en la base de datos.',
        'na': 'N/D',
        'home_button': 'Inicio',
        'disclaimer': 'Este es un sitio de portafolio de demostración. La búsqueda de productos está limitada solo a productos alimenticios.',
    },
}


def get_lang():
    """Read the language code from the request parameters (GET or POST).
    Falls back to DEFAULT_LANG if the value is not in SUPPORTED_LANGS,
    so arbitrary strings never reach the template."""
    lang = request.values.get('lang', DEFAULT_LANG)
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def allowed_file(filename):
    """Return True if the filename has an accepted extension.
    rsplit('.', 1) splits on the last dot only, correctly handling names
    like 'photo.bak.jpg' where multiple dots are present."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def lookup_product(barcode, lang):
    """Query Open Food Facts and translate the text fields into the chosen language.

    Returns a dict with name/brand/category/quantity, or None if the product
    is not found in the database (status != 1).

    Translation note: source='auto' is required because Open Food Facts stores
    data in the contributor's language, which varies per product (often French
    or English). Brand names are intentionally NOT translated as they are proper nouns.
    """
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    response = requests.get(url, headers={"User-Agent": "MyPortfolioApp/1.0"}, timeout=10)
    data = response.json()

    # status == 1 means the product was found; any other value means not found.
    if data.get("status") != 1:
        return None

    product = data["product"]
    na = TRANSLATIONS[lang]['na']                              # fallback for empty fields
    translator = GoogleTranslator(source='auto', target=lang)

    name_raw = product.get("product_name", "")
    name_translated = translator.translate(name_raw) if name_raw else na

    # 'categories' is a comma-separated string (e.g. "Snacks, Biscuits, ...").
    # Google Translate handles comma-separated term lists correctly.
    categories_raw = product.get("categories", "")
    categories_translated = translator.translate(categories_raw) if categories_raw else na

    return {
        "name": name_translated,
        "brand": product.get("brands") or na,  # not translated: proper noun
        "category": categories_translated,
        "quantity": product.get("quantity") or na,
    }


@app.route("/", methods=["GET"])
def index():
    """Home page: renders the upload form with the language switcher.
    scanned is not passed here (defaults to falsy in the template) because
    this is the initial state, not a result page."""
    lang = get_lang()
    return render_template("index.html", t=TRANSLATIONS[lang], lang=lang)


@app.route("/scan", methods=["POST"])
def scan():
    """Receive the uploaded image, run the three-step pipeline, and render
    the result (or an error message) back on index.html.

    scanned=True is passed to the template on every response from this route:
    - disables the language switcher (language was already chosen before upload)
    - shows the Home button so the user can go back to the upload page
    """
    lang = get_lang()
    t = TRANSLATIONS[lang]

    # --- Input validation ---
    file = request.files.get("image")
    if not file or file.filename == "":
        return render_template("index.html", t=t, lang=lang, error=t['error_no_file'], scanned=True)
    if not allowed_file(file.filename):
        return render_template("index.html", t=t, lang=lang, error=t['error_format'], scanned=True)

    # --- Temporary file ---
    # delete=False is required on Windows: the Cloudmersive SDK opens the file
    # by path after the context manager exits, so the file must still exist on disk.
    # The finally block guarantees cleanup regardless of success or exception.
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # --- Step 1: barcode reading (Cloudmersive) ---
    try:
        scan_response = scan_api.barcode_scan_image(tmp_path)
    except ApiException:
        # ApiException covers SDK-level HTTP errors (e.g. HTTP 500 from a blurry image).
        return render_template("index.html", t=t, lang=lang, error=t['error_scan'], scanned=True)
    finally:
        # Always delete the temp file, even if an exception was raised above.
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # successful is False when the image contains no readable barcode.
    if not scan_response.successful:
        return render_template("index.html", t=t, lang=lang, error=t['error_no_barcode'], scanned=True)

    # --- Steps 2 + 3: product lookup and translation (Open Food Facts + Google Translate) ---
    barcode = scan_response.raw_text
    product = lookup_product(barcode, lang)
    if product is None:
        error = t['error_not_found'].format(barcode=barcode)
        return render_template("index.html", t=t, lang=lang, error=error, scanned=True)

    return render_template("index.html", t=t, lang=lang, product=product, barcode=barcode, scanned=True)


if __name__ == "__main__":
    app.run(debug=True)
