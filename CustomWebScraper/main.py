import csv
import os
import re
import time
import warnings

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

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

REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')


def clean_nutrient_name(name: str) -> str:
    """Restore spaces stripped by HTML rendering: 'Thiamin[B1]' → 'Thiamin [B1]', 'A+B' → 'A + B'."""
    name = re.sub(r'(?<! )\[', ' [', name)
    name = re.sub(r'(?<! )\+(?! )', ' + ', name)
    return name


def split_amount_unit(text: str) -> tuple[str, str]:
    """Split '0.811\xa0mg' into ('0.811', 'mg'), or '91.0 g' into ('91.0', 'g')."""
    parts = text.replace('\xa0', ' ').split(' ', 1)
    return parts[0], parts[1].strip() if len(parts) > 1 else ''


def clean_dv(text: str) -> str:
    """'68\xa0%' → '68 %', '' → ''."""
    return text.replace('\xa0', ' ').strip()


def food_name_to_filename(food_name: str) -> str:
    """'Pasta, enriched, dry' → 'pasta_enriched_dry.csv'."""
    name = food_name.lower()
    name = re.sub(r'[,\s%]+', '_', name)
    name = re.sub(r'[^a-z0-9_]', '', name)
    return name.strip('_') + '.csv'


def scrape(url: str) -> dict:
    response = requests.get(url, headers=REQUEST_HEADERS, verify=False, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    food_name_el = soup.find(id='food-name')
    if not food_name_el:
        raise ValueError('Food detail page not found — got a search results page instead')
    food_name = food_name_el.get_text(strip=True)

    # Serving size from the selected <option>: "1.0 cup spaghetti = 91.0 g"
    select_el = soup.find('select', class_='serving')
    selected_opt = select_el.find('option', selected=True) if select_el else None
    serving_str = selected_opt.get_text(strip=True) if selected_opt else ''

    if '=' in serving_str:
        description, right = serving_str.rsplit('=', 1)
        description = description.strip()
        amount, unit = split_amount_unit(right.strip())
    elif serving_str:
        amount, unit = split_amount_unit(serving_str)
        description = ''
    else:
        amount, unit, description = '', '', ''

    calories_el = soup.find(id='calories')
    calories = calories_el.get_text(strip=True) if calories_el else ''

    nutrients = []
    for table in soup.find_all('table', class_='nutrient'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text(strip=True) for c in cells]

            if len(texts) < 2:
                continue  # section header (1 cell)

            if texts[0] == 'Nutrient':
                continue  # column header row

            # Skip chart/pie-description rows (very long first cell)
            if any(len(t) > 100 for t in texts):
                continue

            # Normal nutrient row: Amount cell contains a non-breaking space separator
            if len(texts) >= 3 and '\xa0' in texts[1]:
                name = clean_nutrient_name(texts[0])
                amt, unit_n = split_amount_unit(texts[1])
                dv = clean_dv(texts[2])
                nutrients.append((name, amt, unit_n, dv))
                continue

            # Special omega ratio row: cell[0] looks like a measurement, e.g. "0.02 g"
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


def write_csv(data: dict) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, food_name_to_filename(data['food_name']))

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Downloaded from'])
        w.writerow(['https://www.nutritionvalue.org'])
        w.writerow([])
        w.writerow(['Food', 'Amount', 'Unit', 'Description'])
        w.writerow([data['food_name'], data['amount'], data['unit'], data['description']])
        w.writerow([])
        w.writerow(['Nutrient', 'Amount', 'Unit', 'DV'])
        w.writerow(['Calories', data['calories'], '', ''])
        for name, amt, unit_n, dv in data['nutrients']:
            w.writerow([name, amt, unit_n, dv])
        w.writerow([])
        w.writerow(['* DV is based on 2000 calories diet.'])
        w.writerow([])
        w.writerow(['Downloaded from'])
        w.writerow(['https://www.nutritionvalue.org'])

    return filepath


if __name__ == '__main__':
    for i, url in enumerate(URL_LIST):
        print(f'Scraping ({i + 1}/{len(URL_LIST)}): {url}')
        try:
            data = scrape(url)
            filepath = write_csv(data)
            print(f'  -> {data["food_name"]}: {len(data["nutrients"])} nutrients → {filepath}')
        except Exception as exc:
            print(f'  ERROR: {exc}')
        if i < len(URL_LIST) - 1:
            time.sleep(2)
