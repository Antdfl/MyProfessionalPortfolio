# Custom Web Scraper — Food Nutrition Data

A Python web scraper that extracts full nutritional profiles from [nutritionvalue.org](https://www.nutritionvalue.org) and exports each food as a structured CSV file.

## Overview

The scraper targets 9 foods, fetches their complete macronutrient and micronutrient data (60–135 data points per food), and writes one CSV per food to an `output/` directory. Every CSV follows a consistent schema: food metadata (name, serving size, unit, description), followed by a full nutrient table (name, amount, unit, % daily value).

### Foods scraped

| Food | Output file |
| ---- | ----------- |
| Pasta, enriched, dry | `pasta_enriched_dry.csv` |
| Chicken breast, oven-roasted, roll | `chicken_breast_ovenroasted_roll.csv` |
| Fish, raw, wild, Atlantic, salmon | `fish_raw_wild_atlantic_salmon.csv` |
| Cheese, 2% milkfat, lowfat, cottage | `cheese_2_milkfat_lowfat_cottage.csv` |
| Broccoli, raw | `broccoli_raw.csv` |
| Apples, with skin, raw | `apples_with_skin_raw.csv` |
| Nuts, almonds | `nuts_almonds.csv` |
| Avocado, raw | `avocado_raw.csv` |
| Quinoa, cooked | `quinoa_cooked.csv` |

## Technical Stack

- **Python 3.10+**
- `requests` — HTTP client
- `beautifulsoup4` — HTML parsing
- `python-dotenv` — environment configuration
- Standard library: `csv`, `re`, `os`, `time`, `warnings`

## Setup

```bash
pip install requests beautifulsoup4 python-dotenv
python main.py
```

CSVs are written to `CustomWebScraper/output/`.

## How It Works

### HTML inspection and element targeting

Before writing any code, the page's raw HTML response was inspected to map each data point to a specific DOM element:

| Data | Selector |
| ---- | -------- |
| Food name | `<h1 id="food-name">` |
| Serving size | `<select class="serving"> > <option selected>` |
| Calories | `<td id="calories">` |
| Nutrient rows | All `<table class="nutrient results">` |

### Data extraction and cleaning

Each nutrient row follows the pattern `['Thiamin[Vitamin B1]', '0.811\xa0mg', '68\xa0%']`. Two transformations normalise the data before writing:

- **Amount / unit split** — the non-breaking space (`\xa0`) between value and unit acts as a reliable separator (e.g. `0.811\xa0mg` → `0.811`, `mg`).
- **Name normalisation** — alternate names are concatenated without spacing in the HTML (`Thiamin[Vitamin B1]`); a regex restores the expected format (`Thiamin [Vitamin B1]`). The same applies to compound names joined by `+` (e.g. `Lutein+zeaxanthin` → `Lutein + zeaxanthin`).

### Filename generation

Food names are lowercased, punctuation and whitespace are collapsed to underscores, and non-alphanumeric characters are stripped:

```text
"Pasta, enriched, dry"  →  pasta_enriched_dry.csv
"Cheese, 2% milkfat, lowfat, cottage"  →  cheese_2_milkfat_lowfat_cottage.csv
```

### Stale URL handling

Three of the original URLs returned search result pages instead of food detail pages (the site had renamed those paths). The scraper raises a descriptive `ValueError` on redirect detection. The correct canonical URLs were identified from the search results and updated in `URL_LIST`.

### Rate limiting

A 2-second pause between requests avoids triggering server-side rate limiting.

## Library Choice: BeautifulSoup vs Selenium WebDriver

The decision was made after inspecting the actual HTTP response, not by assumption.

All nutrition data on nutritionvalue.org is **server-side rendered** — the full nutrient tables are present in the initial HTML response, before any JavaScript executes. The site's "Please enable JavaScript" notice only gates the interactive UI (food diary, calculators, charts).

| Criteria | BeautifulSoup + requests | Selenium WebDriver |
| -------- | ------------------------ | ------------------ |
| Data in initial HTML | Yes — all nutrient tables present | Would wait for JS unnecessarily |
| Speed | ~1 sec / page | 5–15 sec / page (browser launch + render) |
| Dependencies | `requests`, `beautifulsoup4` | Chrome/Firefox binary + WebDriver |
| Complexity | Straightforward | Requires explicit waits, browser config |
| Resource usage | Minimal | Full browser process per session |

Selenium would be the correct choice if data were loaded via JavaScript after page load, if login/click-through flows were required, or if heavy bot-detection challenges (e.g. CAPTCHAs) blocked static requests. None of those conditions apply here.

## CSV Output Format

```csv
Downloaded from
https://www.nutritionvalue.org

Food,Amount,Unit,Description
"Pasta, enriched, dry",91.0,g,1.0 cup spaghetti

Nutrient,Amount,Unit,DV
Calories,338,,
"Vitamin A, RAE",0.00,mcg,0 %
"Thiamin [Vitamin B1]",0.811,mg,68 %
...

* DV is based on 2000 calories diet.

Downloaded from
https://www.nutritionvalue.org
```
