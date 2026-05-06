# Amazon Scraper

Scrapes Amazon search results using Selenium with undetected-chromedriver to bypass basic bot detection.

## Quick Start

```bash
uv run scraper
```

Or run directly:

```bash
uv run python -m scraper.cli
```

## Configuration

Edit `src/scraper/config.py` to change:

| Setting | Default | Description |
|---|---|---|
| `keyword` | `mechanical keyboard` | Search term |
| `pages` | `3` | Number of result pages to scrape |
| `headless` | `False` | Run browser headlessly (not recommended) |
| `output_dir` | `amazon_output` | Directory for CSV/HTML output |

## Output

Files are saved to `amazon_output/`:
- `amazon_<keyword>_<timestamp>.csv` — structured product data
- `amazon_<keyword>_<timestamp>.html` — raw page HTML

## Project Structure

```
scraper/
├── src/scraper/
│   ├── __init__.py
│   ├── cli.py          # Entry point
│   ├── config.py       # Configuration
│   ├── driver.py       # Chrome driver setup
│   ├── extractor.py    # Product data extraction
│   ├── scraper.py      # Main scraping logic
│   └── utils.py        # Helper functions
├── tests/
├── pyproject.toml
└── README.md
```
