# Space Race Data Analysis

## Overview

This project applies data exploration, cleaning, and visualisation techniques to a historical dataset of space missions sourced from [nextspaceflight.com](https://nextspaceflight.com). The dataset covers all launches since the beginning of the Space Race between the USA and the Soviet Union in 1957 and includes information on mission outcomes, launch costs, organisations involved, and geographic origins.

The goal is to turn raw data into insight by asking meaningful questions and answering them visually.

---

## Research Questions

The analysis is driven by the following questions:

- Which organisations and countries have been the most prolific launchers over time?
- How has the cost of a space mission evolved across decades?
- Are there seasonal patterns in when launches are scheduled?
- Has the mission failure rate improved over the history of spaceflight?
- How did the Cold War rivalry between the USA and USSR play out in terms of launch volume?

---

## Methodology

### 1. Preliminary Exploration

Before any cleaning or visualisation, the dataset is inspected to understand its shape, column types, and the extent of missing values. This step establishes a baseline and surfaces any immediate data quality issues (wrong types, unexpected nulls, inconsistent naming).

### 2. Data Cleaning

The raw dataset requires several transformations before it is fit for analysis:

- **Removing irrelevant columns** — artefact columns introduced by the export process are dropped.
- **Parsing dates** — the date field is stored as a plain string and must be converted to a proper datetime type so that time-based aggregations (by year, by month) are possible.
- **Normalising categorical values** — country and location names contain inconsistencies (e.g. sea-launch coordinates attributed to no country) that must be resolved before grouping.
- **Handling missing values** — the cost field has significant gaps; rows with missing cost are excluded when computing price-related metrics, but retained for all other analyses.
- **Type conversion** — numeric fields stored as strings are cast to the appropriate numeric type.

### 3. Exploratory Analysis

Once the data is clean, aggregations are computed to answer each research question. Typical operations include grouping by organisation, country, or time period, counting launches, computing averages, and deriving failure rates.

### 4. Visualisation

Each insight is represented with the chart type best suited to the underlying question:

| Question type | Chart type |
| --- | --- |
| Ranking (e.g. most launches per organisation) | Horizontal bar chart |
| Proportion / composition | Pie or donut chart |
| Distribution (e.g. launch costs) | Histogram |
| Geographic distribution | Choropleth map |
| Hierarchical breakdown | Sunburst chart |
| Trend over time | Line chart |
| Year-on-year comparison between two parties | Grouped / dual-line chart |

All charts are built with Plotly Express and rendered interactively inside the notebook.

---

## Tools & Libraries

| Purpose | Library |
| --- | --- |
| Data manipulation | pandas |
| Interactive visualisation | Plotly Express |
| Static / supplementary charts | Matplotlib, Seaborn |

---

## Dataset

Source: [nextspaceflight.com](https://nextspaceflight.com)  
Scope: All recorded space missions from 1957 to the present  
Key fields: mission name, organisation, country, launch date, mission status, rocket status, launch cost
