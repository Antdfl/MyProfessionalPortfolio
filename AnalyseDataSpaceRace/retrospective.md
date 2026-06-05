# Retrospective — Analyse Data: Space Race (1957–2020)

**Dataset:** mission_launches.csv — 4,324 missioni spaziali da nextspaceflight.com  
**Stack:** Python · pandas · Plotly · Jupyter Notebook · iso3166

---

## Part 1 — Technical Challenges & Lessons Learned
*For technical recruiters and hiring managers*

### Skills Demonstrated

**Data Wrangling with pandas**
- `pd.to_datetime()` with `format='mixed'` and `utc=True` to handle dates with inconsistent formats and mixed timezones across 60 years of records
- `.dt.to_period('M')` for month-level time series aggregation; discovered that `Period` objects are not JSON-serialisable and must be converted with `.astype(str)` before passing to Plotly
- `groupby().size().reset_index(name=...)` as the standard pattern for counting occurrences per group
- `.rolling(window=12).mean()` for smoothing noisy monthly launch data; result stored in a new column to avoid overwriting source data
- `.replace(dict)` — understood that pandas applies the mapping in a single pass, so chaining (A→B, B→C in the same dict) does not cascade; fix: map directly to the final value
- `groupby().idxmax()` to extract the row with the maximum value per group (e.g. leading country per year)
- `.isin()` combined with `.loc[]` for multi-value filtering and conditional column assignment

**Data Visualisation with Plotly**
- `go.Choropleth` with `locationmode='ISO-3'` for world maps; used the `iso3166` library to convert country names to ISO Alpha-3 codes with a correction dictionary for non-standard names (e.g. Yellow Sea → China, Baikonur → Russian Federation/Kazakhstan)
- `px.sunburst` for hierarchical data (Country → Organisation → Mission Status)
- `px.line` and `px.bar` with `color=` parameter for multi-series charts; learned the difference between `color_discrete_sequence` (list of colours) and `color_continuous_scale` (string, not list)
- `make_subplots(specs=[[{"secondary_y": True}]])` from `plotly.subplots` for dual-axis charts; combined with `go.Scatter` and `fig.add_trace(..., secondary_y=True/False)`
- `fig.update_yaxes(title_text=..., secondary_y=True/False)` to set axis titles independently on dual-axis charts
- `colorbar=dict(len=..., thickness=..., title=dict(text=..., font=dict(size=...)))` — nested syntax for Choropleth legend customisation

### Key Bugs Encountered and Fixed

| # | Problem | Root Cause | Fix |
|---|---------|-----------|-----|
| 1 | Country names unmapped to ISO-3 | `pandas.replace()` is single-pass; A→B, B→C in the same dict doesn't chain | Map every value directly to its final ISO-standard name |
| 2 | `TypeError: Period not JSON serializable` | `.dt.to_period('M')` produces `Period` objects incompatible with Plotly | `.astype(str)` before passing to chart |
| 3 | DataFrame corrupted (2 rows instead of 2,500+) | `cold_war_df` created as a view, not a copy — SettingWithCopyWarning silently dropped assignments | Added `.copy()` to the filter: `clean_df[...].copy()` |
| 4 | Variable overwritten mid-notebook | Assigned groupby result back to `cold_war_df` instead of a new variable | Renamed aggregation variables to avoid clobbering source DataFrames |
| 5 | `ImportError: cannot import make_subplots from plotly.graph_objects` | Wrong module path | Correct import: `from plotly.subplots import make_subplots` |
| 6 | `px.line()` got unexpected keyword `secondary_y` | `px` functions and `make_subplots` cannot be mixed | Use `go.Scatter` with `fig.add_trace()` when using `make_subplots` |
| 7 | Horizontal bar chart showed lowest value at top | Plotly renders horizontal bars bottom-to-top | Two-step sort: descending to select top-N, then ascending for correct visual order |
| 8 | Rolling average overwrote launch counts | Assigned result back to the source column | Created a separate `Rolling_Avg` column |

---

## Part 2 — What the Data Tells Us
*For business managers — no code required*

### The Space Race Was Won by the USSR — On Volume

During the Cold War (1957–1991), the Soviet Union launched **72.6% of all space missions**, compared to just 27.4% for the United States. The USSR's strategy was quantity: their military space programme (RVSN USSR) was launching up to **90 rockets per year** in the mid-1970s — a pace never matched before or since by any single organisation.

### The 1970s Were the Peak of Human Space Activity

Space launches peaked around **1975–1976**, driven almost entirely by Soviet military satellite programmes. After 1977, the USSR dramatically cut its launch rate — the Cold War space arms race was quietly winding down more than a decade before the USSR's political collapse in 1991.

### We Got Much Better at It — Very Quickly

In the late 1950s, more than **70% of launches failed**. By the 1970s, the failure rate had already dropped below 10%. By 2000, it was under 5%. This dramatic learning curve reflects 20 years of intense engineering investment during the space race, driven by competition between two superpowers with unlimited budgets.

### More Launches Today — Same Low Failure Rate

After 2015, the total number of launches started climbing again, reaching levels not seen since the Cold War. Yet the failure rate did **not** increase — it remained stable at around 5–8%. This means the new generation of space companies is launching more often without sacrificing reliability.

### China Is the New Space Superpower

From 2018 to 2020, **CASC (China Aerospace Science and Technology Corporation)** was the single most active space organisation in the world, surpassing NASA, Roscosmos, and all other players. China's rise in space is not a future ambition — it has already happened.

### SpaceX Is Rewriting the Rules

SpaceX appeared in the data only after 2010, but by 2020 it was already challenging CASC for the top position. SpaceX's Falcon 9, driven by the Starlink satellite constellation programme, has made the United States competitive again in launch volume — something that had not happened since the Cold War.

### December Is the Busiest Month for Launches

Launches are not evenly distributed across the year. December consistently sees the highest number of missions — likely driven by annual budget cycles and programme deadlines. March and April tend to be quieter.

### NASA Spent the Most — Per Launch

While NASA did not lead in volume, it led in expenditure. NASA's total budget for space missions far exceeded any other organisation's, and its cost per launch was also among the highest — reflecting its focus on high-value scientific and crewed missions rather than repetitive satellite deployments.

### The Geography of Space Has Changed

During the Cold War, space launches came from just two countries: the USA and the USSR (including launches from Baikonur Cosmodrome in Kazakhstan). Today, active spacefaring nations include China, India, Japan, South Korea, France (via Arianespace), and several others. Space is no longer a two-player game.
