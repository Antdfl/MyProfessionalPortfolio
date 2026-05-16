# Project Retrospective — Custom Web Scraper

**Author:** Antonio Di Felice  
**Date:** May 2026  
**Platform:** Python script

---

## Project Overview

A Python web scraper that extracts full nutritional profiles (macronutrients, micronutrients, amino acids, and fatty acids) from nutritionvalue.org and exports one structured CSV file per food. Nine foods are targeted, producing 9 CSV files with 60–135 nutrient rows each.

---

## What Went Well

- Confirmed the correct library choice (BeautifulSoup) by inspecting the actual HTTP response before writing any scraping code, rather than guessing.
- Identified reliable, stable HTML selectors: each data point mapped to a unique element (`id="food-name"`, `id="calories"`, `class="serving"`, `class="nutrient results"`).
- Discovered and exploited the non-breaking space (`\xa0`) as a built-in separator between amount and unit values — this made splitting both robust and dependency-free.
- The nutrient name normalisation handled all edge cases in one regex pass, producing output that matched the expected CSV format exactly.
- Error detection for stale URLs was explicit: raising a descriptive `ValueError` rather than silently writing an empty or malformed CSV.
- The 2-second inter-request delay prevented any rate-limiting issues across all 9 requests.

---

## Implementation Challenges

### 1. URL percent-encoding caused a misleading test failure

During the initial exploration, a test script passed the URL to Python using `%%2C` to escape the `%` character inside a bash `-c` command. Python received the string literally as `%%2C` (two percent signs), so requests sent the wrong path to the server. The server interpreted this as a search query and returned a search results page — which had no `id="food-name"` element and no nutrient tables.

This was confusing because the server still returned HTTP 200, and the page looked superficially correct. Only after checking the response `<title>` and final URL did it become clear the server had silently redirected to the search endpoint.

**Resolution:** Switched to using the exact URL string from `URL_LIST` without any shell escaping. The correct Python string literal `'Pasta%2C_enriched%2C_dry_nutritional_value.html'` passes `%2C` unchanged to `requests`, which the server correctly decodes as a comma.

**Lesson learned:** When testing URLs from the command line, double-encoding is a subtle and silent failure mode — the HTTP status stays 200 and the page looks real. Always verify the final URL in `response.url` and check for a known anchor element rather than assuming the response is correct.

---

### 2. A "JavaScript-required" banner suggested the data was dynamically loaded — it was not

The page's `<noscript>` block prominently displays "Please enable JavaScript in order to use this website", and the page also has Cloudflare protection scripts. Both signals suggested the nutrition data might be loaded via AJAX after page load, which would have made BeautifulSoup insufficient and Selenium necessary.

Inspecting the raw HTML response showed the opposite: the full nutrient tables — all 7 categories with every row — are present in the initial server response. The JavaScript banner gates only the interactive UI (food diary, nutrition calculator, charts). The data itself is server-side rendered.

**Resolution:** Confirmed the architecture before choosing a library. BeautifulSoup was the right tool; Selenium would have added browser dependencies, a 5–15× slowdown, and significant setup complexity for no benefit.

**Lesson learned:** Never infer rendering strategy from a "JavaScript required" banner or the presence of a JS framework. Inspect the actual HTTP response. The distinction between SSR data and JS-loaded data must be verified empirically, not assumed.

---

### 3. Three of the nine URLs in `URL_LIST` were stale

When the full run was executed, 6 of 9 URLs succeeded. The remaining three — broccoli, apple, and almonds — were silently redirected by the server to generic search results pages. The site had renamed those food paths at some point after the URL list was authored.

The search results pages returned HTTP 200 (not 404 or 301 visible at the application level), with a results table populated entirely via JavaScript — meaning the correct canonical links were not in the raw HTML either.

**Resolution:** The correct URLs were found by testing alternate naming conventions derived from the USDA database format:

| Original (stale) | Correct |
| ---------------- | ------- |
| `Vegetables%2C_raw%2C_broccoli` | `Broccoli%2C_raw` |
| `Apple%2C_raw%2C_with_skin` | `Apples%2C_with_skin%2C_raw` |
| `Almonds%2C_raw` | `Nuts%2C_almonds` |

**Lesson learned:** Hardcoded URL lists rot. Even on a single scraping run, a meaningful fraction of paths may have changed. A more resilient approach would auto-detect the redirect to a search page and follow the first result, rather than raising and stopping. This would be the right improvement for a production scraper.

---

### 4. The fats table contained a non-standard row that broke the extraction logic

All nutrient tables follow the same structure: a section header row, a column header row, then data rows of `[name, amount\xa0unit, DV%]`. The fats table contained two extra rows not present in any other category:

- A chart description row with 7 cells and several hundred characters of text.
- An omega-3/omega-6 ratio row with 3 cells but no `\xa0` separator, structured as `['0.02 g', '', '0.00']`.

The generic extraction logic (which relied on `\xa0` as a marker for valid nutrient rows) silently skipped both rows, producing an incomplete fats section.

**Resolution:** Added two explicit guards:

- Skip rows where any cell exceeds 100 characters (catches the chart description row).
- Detect the omega ratio row by matching `r'^[\d.]+\s+\w+$'` on the first cell and write it with `'undefined'` as the unit, matching the format in the CSV reference template.

**Lesson learned:** Real-world HTML tables almost always have at least one row that does not fit the expected pattern. Extraction logic should be written defensively: handle the common case cleanly, and add explicit guards for known exceptions rather than assuming a uniform structure.

---

### 5. SSL certificate verification failed on the first request

The first attempt to fetch a page raised `ssl.SSLCertVerificationError` with "unable to get local issuer certificate". This is a known Windows/Python issue where the system's CA bundle is not automatically trusted by `urllib3`.

**Resolution:** Added `verify=False` to all `requests.get()` calls and suppressed the resulting `InsecureRequestWarning` via `warnings.filterwarnings`. For a public portfolio scraper against a well-known domain this is an acceptable trade-off.

**Lesson learned:** SSL verification failures on Windows are a common environment issue, not a code defect. The correct long-term fix is to install the `certifi` package and pass `verify=certifi.where()`, which avoids suppressing warnings while resolving the root cause.


---

## Test Results

The full run against all 9 URLs produced the following outcomes:

| # | Food | Nutrients extracted | Result |
| - | ---- | ------------------- | ------ |
| 1 | Pasta, enriched, dry | 126 | OK |
| 2 | Chicken breast, oven-roasted, roll | 88 | OK |
| 3 | Fish, raw, wild, Atlantic, salmon | 68 | OK |
| 4 | Cheese, 2% milkfat, lowfat, cottage | 135 | OK |
| 5 | Broccoli, raw | 116 | OK (URL corrected) |
| 6 | Apples, with skin, raw | 104 | OK (URL corrected) |
| 7 | Nuts, almonds | 128 | OK (URL corrected) |
| 8 | Avocado, raw | 66 | OK |
| 9 | Quinoa, cooked | 97 | OK |

All 9 CSV files were verified against the reference schema: correct header, food metadata row, full nutrient table, DV footnote, and footer.

### Final Considerations

- The stale URL problem (challenge 3) is the most significant design gap. A scraper that fails on 33% of its inputs without a self-correction mechanism is not production-ready. Auto-following the first search result would make the tool self-correcting.
- The `verify=False` workaround for SSL should be replaced with `certifi` before any deployment beyond a local portfolio.
- The 2-second delay was sufficient for 9 requests but would need tuning for larger-scale runs. The scraper has no retry logic for transient network errors — adding exponential backoff (as implemented in the PDF-to-audiobook project) would make it more resilient.

---

## Architectural Observations for Future Projects

**Auto-follow search redirects**  
When the server redirects a food URL to a search results page, the scraper should detect this, extract the first result link, and follow it automatically. This would reduce maintenance overhead as the site's URL structure evolves.

**Centralise selectors as constants**  
The CSS selectors and element IDs (`food-name`, `calories`, `serving`, `nutrient`) are embedded in the scraping logic. Defining them as named constants at module level would make the scraper easier to update if the site redesigns its HTML.

**Add a `--dry-run` flag**  
A dry-run mode that fetches pages and reports what would be written — without creating files — would be useful for validating a new URL list before a full run.

**Replace `verify=False` with `certifi`**  
`pip install certifi` and `verify=certifi.where()` resolves the SSL issue properly without suppressing warnings, and is the standard approach for Python projects on Windows.

---

## Summary

The core engineering work in this project was not the scraping itself — mapping selectors and reading rows is straightforward. The real challenges were the invisible failure modes: a URL that redirects silently to a search page, an HTML banner that implies dynamic rendering when the data is actually static, a bash escaping mistake that produced a convincing but wrong response, and a single non-standard row that broke an otherwise uniform table structure. Each of these required stepping back from the code and inspecting the actual HTTP response directly, rather than reasoning from assumptions about how the site ought to work.
