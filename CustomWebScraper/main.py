"""
Custom Web Scraper — Food Nutrition Data
=========================================
Scrapes nutritional profiles from nutritionvalue.org and writes one CSV file
per food to the output/ directory.

Each CSV contains:
  - A food metadata row  (name, serving amount, unit, description)
  - A full nutrient table (name, amount, unit, % daily value)
  covering vitamins, minerals, proteins/amino acids, carbohydrates,
  fats/fatty acids, sterols, and miscellaneous nutrients.

Usage:
    python main.py

Output files land in:  CustomWebScraper/output/<food_name>.csv

Dependencies:
    pip install requests beautifulsoup4

Notes:
  - SSL verification is disabled (verify=False) due to a Windows CA-bundle
    issue with urllib3. Replace with verify=certifi.where() in production.
  - A 2-second pause between requests avoids server-side rate limiting.
  - If a URL redirects to a search page (stale path), the script prints an
    error and moves on rather than writing a malformed CSV.
"""

import csv
import os
import re
import time
import warnings

import requests
from bs4 import BeautifulSoup

# Suppress the InsecureRequestWarning that fires because verify=False is set.
# This is intentional — see the module docstring for context.
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# One URL per food.  The paths use percent-encoded commas (%2C) exactly as the
# server expects them.  Do NOT double-encode (%%2C) — that sends the wrong path.
URL_LIST = [
    "https://www.nutritionvalue.org/Pasta%2C_enriched%2C_dry_nutritional_value.html",
    "https://www.nutritionvalue.org/Chicken_breast%2C_oven-roasted%2C_roll_nutritional_value.html",
    "https://www.nutritionvalue.org/Fish%2C_raw%2C_wild%2C_Atlantic%2C_salmon_nutritional_value.html",
    "https://www.nutritionvalue.org/Cheese%2C_2%25_milkfat%2C_lowfat%2C_cottage_nutritional_value.html",
    "https://www.nutritionvalue.org/Broccoli%2C_raw_nutritional_value.html",
    "https://www.nutritionvalue.org/Apples%2C_with_skin%2C_raw_nutritional_value.html",
    "https://www.nutritionvalue.org/Nuts%2C_almonds_nutritional_value.html",
    "https://www.nutritionvalue.org/Avocado%2C_raw_nutritional_value.html",
    "https://www.nutritionvalue.org/Quinoa%2C_cooked_nutritional_value.html",
]

# Mimic a real browser so the server does not reject the request as a bot.
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}

# Always write CSV files next to this script, regardless of where the script
# is launched from.  os.path.abspath(__file__) gives the script's own path.
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def clean_nutrient_name(name: str) -> str:
    """Restore spaces that the site's HTML strips from nutrient names.

    The site renders alternate names and compound names without spacing:
      'Thiamin[Vitamin B1]'   →  'Thiamin [Vitamin B1]'
      'Lutein+zeaxanthin'     →  'Lutein + zeaxanthin'

    Two regex substitutions handle both cases:
      - Insert a space before '[' when not already preceded by one.
      - Insert spaces around '+' when not already surrounded by spaces.
    """
    name = re.sub(r'(?<! )\[', ' [', name)
    name = re.sub(r'(?<! )\+(?! )', ' + ', name)
    return name


def split_amount_unit(text: str) -> tuple[str, str]:
    """Split a combined amount-unit string into its two parts.

    The site separates amount from unit with a non-breaking space (\\xa0),
    which acts as a reliable delimiter that is never part of a number or unit.

    Examples:
        '0.811\\xa0mg'  →  ('0.811', 'mg')
        '91.0 g'        →  ('91.0',  'g')    # plain space also handled
        '338'           →  ('338',   '')      # no unit (e.g. Calories)
    """
    parts = text.replace('\xa0', ' ').split(' ', 1)
    return parts[0], parts[1].strip() if len(parts) > 1 else ''


def clean_dv(text: str) -> str:
    """Normalise a % Daily Value string by replacing non-breaking spaces.

    Examples:
        '68\\xa0%'  →  '68 %'
        ''          →  ''        (many nutrients have no DV reference)
    """
    return text.replace('\xa0', ' ').strip()


def food_name_to_filename(food_name: str) -> str:
    """Convert a food name to a safe, lowercase filename.

    Steps:
        1. Lowercase the full name.
        2. Collapse commas, whitespace, and percent signs into underscores.
        3. Strip any remaining characters that are not letters, digits, or underscores.
        4. Trim leading/trailing underscores and append '.csv'.

    Examples:
        'Pasta, enriched, dry'               →  'pasta_enriched_dry.csv'
        'Cheese, 2% milkfat, lowfat, cottage' →  'cheese_2_milkfat_lowfat_cottage.csv'
    """
    name = food_name.lower()
    name = re.sub(r'[,\s%]+', '_', name)
    name = re.sub(r'[^a-z0-9_]', '', name)
    return name.strip('_') + '.csv'


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape(url: str) -> dict:
    """Fetch a nutritionvalue.org food page and extract its nutritional data.

    The site is server-side rendered: all nutrient tables are present in the
    initial HTML response, so BeautifulSoup is sufficient — no JavaScript
    execution (Selenium) is required.

    DOM elements targeted:
        <h1 id="food-name">          — food name
        <select class="serving">     — portion-size dropdown; the selected
                                       <option> gives amount and description
        <td id="calories">           — calorie count for the selected portion
        <table class="nutrient …">   — one table per nutrient category
                                       (vitamins, minerals, proteins, etc.)

    Args:
        url: Full URL of the food detail page.

    Returns:
        A dict with keys: food_name, amount, unit, description, calories,
        nutrients (list of (name, amount, unit, dv) tuples).

    Raises:
        ValueError: If the server redirects to a search results page instead
                    of a food detail page (happens when a URL path is stale).
        requests.HTTPError: On any non-2xx HTTP response.
    """
    response = requests.get(url, headers=REQUEST_HEADERS, verify=False, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    # --- Food name -----------------------------------------------------------
    # Present only on food detail pages.  Its absence means the server
    # redirected us to a search results page (stale URL).
    food_name_el = soup.find(id='food-name')
    if not food_name_el:
        raise ValueError('Food detail page not found — got a search results page instead')
    food_name = food_name_el.get_text(strip=True)

    # --- Serving size --------------------------------------------------------
    # The dropdown lists options like "1.0 cup spaghetti = 91.0 g".
    # The selected option is the default portion shown on the page.
    # We split on the last '=' to separate the human-readable description
    # (left) from the numeric amount + unit (right).
    select_el = soup.find('select', class_='serving')
    selected_opt = select_el.find('option', selected=True) if select_el else None
    serving_str = selected_opt.get_text(strip=True) if selected_opt else ''

    if '=' in serving_str:
        # e.g. "1.0 cup spaghetti = 91.0 g"  →  desc="1.0 cup spaghetti", amount="91.0", unit="g"
        description, right = serving_str.rsplit('=', 1)
        description = description.strip()
        amount, unit = split_amount_unit(right.strip())
    elif serving_str:
        # e.g. "100 g"  →  amount="100", unit="g", no description
        amount, unit = split_amount_unit(serving_str)
        description = ''
    else:
        amount, unit, description = '', '', ''

    # --- Calories ------------------------------------------------------------
    # Displayed as a large number in the nutrition label; no unit on the page.
    calories_el = soup.find(id='calories')
    calories = calories_el.get_text(strip=True) if calories_el else ''

    # --- Nutrient tables -----------------------------------------------------
    # The page contains 7 <table class="nutrient results"> elements, one per
    # category.  Every table shares the same row structure:
    #
    #   Row 1:  1 cell  — category heading (e.g. "Vitamins")        → skip
    #   Row 2:  3 cells — column headers "Nutrient | Amount | DV"   → skip
    #   Row N:  3 cells — data: name | "value\xa0unit" | "dv\xa0%"  → extract
    #
    # Exception — the Fats table has two non-standard rows:
    #   • A chart-description row with 7 cells and ~300 chars of text  → skip
    #   • An omega-3/omega-6 ratio row: ["0.02 g", "", "0.00"]        → keep as-is
    nutrients = []
    for table in soup.find_all('table', class_='nutrient'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text(strip=True) for c in cells]

            # Single-cell rows are category headings — nothing to extract.
            if len(texts) < 2:
                continue

            # The column header row starts with the literal word "Nutrient".
            if texts[0] == 'Nutrient':
                continue

            # The fats chart-description row is extremely long.
            # Any row containing a cell over 100 chars is structural noise.
            if any(len(t) > 100 for t in texts):
                continue

            # --- Normal nutrient row -----------------------------------------
            # The amount cell always contains a non-breaking space (\xa0)
            # separating the numeric value from its unit.  This is the most
            # reliable signal that a row carries real nutrient data.
            if len(texts) >= 3 and '\xa0' in texts[1]:
                name = clean_nutrient_name(texts[0])
                amt, unit_n = split_amount_unit(texts[1])
                dv = clean_dv(texts[2])
                nutrients.append((name, amt, unit_n, dv))
                continue

            # --- Special omega-ratio row -------------------------------------
            # Structure: ["0.02 g", "", "0.00"]
            # cell[0] matches a plain "number unit" pattern (e.g. "0.02 g").
            # There is no unit column, so we write 'undefined' to signal that,
            # matching the format of the reference CSV template.
            if len(texts) == 3 and re.match(r'^[\d.]+\s+\w+$', texts[0]):
                nutrients.append((texts[0], texts[1], 'undefined', texts[2]))

    return {
        'food_name': food_name,
        'amount': amount,
        'unit': unit,
        'description': description,
        'calories': calories,
        'nutrients': nutrients,
    }


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(data: dict) -> str:
    """Write the scraped data for one food to a CSV file.

    The output format matches the reference schema defined in README.md:

        Downloaded from
        https://www.nutritionvalue.org

        Food,Amount,Unit,Description
        <food row>

        Nutrient,Amount,Unit,DV
        Calories,<value>,,
        <nutrient rows …>

        * DV is based on 2000 calories diet.

        Downloaded from
        https://www.nutritionvalue.org

    newline='' is required by the csv module on Windows to prevent it from
    writing an extra blank line between rows (the module adds its own \\r\\n).

    Args:
        data: Dict returned by scrape().

    Returns:
        Absolute path of the written CSV file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, food_name_to_filename(data['food_name']))

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)

        # Header block
        w.writerow(['Downloaded from'])
        w.writerow(['https://www.nutritionvalue.org'])
        w.writerow([])

        # Food metadata
        w.writerow(['Food', 'Amount', 'Unit', 'Description'])
        w.writerow([data['food_name'], data['amount'], data['unit'], data['description']])
        w.writerow([])

        # Nutrient table — Calories first (no unit), then all other nutrients
        w.writerow(['Nutrient', 'Amount', 'Unit', 'DV'])
        w.writerow(['Calories', data['calories'], '', ''])
        for name, amt, unit_n, dv in data['nutrients']:
            w.writerow([name, amt, unit_n, dv])

        # Footer block
        w.writerow([])
        w.writerow(['* DV is based on 2000 calories diet.'])
        w.writerow([])
        w.writerow(['Downloaded from'])
        w.writerow(['https://www.nutritionvalue.org'])

    return filepath


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    for i, url in enumerate(URL_LIST):
        print(f'Scraping ({i + 1}/{len(URL_LIST)}): {url}')
        try:
            data = scrape(url)
            filepath = write_csv(data)
            print(f'  -> {data["food_name"]}: {len(data["nutrients"])} nutrients → {filepath}')
        except Exception as exc:
            print(f'  ERROR: {exc}')

        # Pause between requests to stay below the server's rate limit.
        # Skipped after the last URL to avoid an unnecessary wait on exit.
        if i < len(URL_LIST) - 1:
            time.sleep(2)
