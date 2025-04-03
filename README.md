# Insider Trading Data Scraper & Visualizer

Python-based tool for scraping and visualizing insider trading data using **SEC** and **OpenInsider** (`openinsider.com`) websites.

---

## Features

- **Dual Data Sources**
  - **SEC Scraper**: Retrieves insider trading data (Form-4 filings) from the SEC Edgar database.
  - **OpenInsider Scraper**: Collects insider trade data from [openinsider.com](http://openinsider.com/).

- **Flexible Data Storage**
  - Supports output to **CSV**, **Excel**, or **SQLite** databases.
  - Options to merge with existing data, append new entries, or overwrite file entirely.

- **Ticker Input Options**
  - Accepts tickers/CIKs as command line arguments or from a text file (one ticker per line).

- **Data Visualization**
  - Generates annotated charts displaying stock prices and insider trade details using [yfinance](https://pypi.org/project/yfinance/) and [seaborn](https://seaborn.pydata.org/).

- **Multi-Processing**
  - The OpenInsider scraper can run with multiple processes to speed up data collection.

- **Customizable Configuration**
  - Configure file paths, date ranges, and other settings via a `.env` file or command line arguments.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/insider-trading-scraper.git
cd insider-trading-scraper
```

### 2. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root with the following content:

```ini
LINK=scrapes.csv         # Default output file path
CSV_SEP=;                # Delimiter for CSV files
NUM_PROCESSES=4          # Number of processes for OpenInsider scraper
USER_AGENT="YourBot/1.0 (YourEmail.com)"  # Required for SEC requests
SEC_BET_REQ=0.2          # SEC request delay in seconds
```

---

## Usage

### 1. Scraping Data

#### **SEC Scraper** (`SEC_insider_scraper.py`)
```bash
# Scrape by ticker/CIK (e.g., Apple and CIK 0000320193)
python SEC_insider_scraper.py AAPL 0000320193 -s sec_data.db

# Scrape from a file and limit to 10 filings per CIK
python SEC_insider_scraper.py -f ciks.txt -l 10 -s sec_data.xlsx
```

| Flag               | Description                                  | Default | Example                 |
|--------------------|----------------------------------------------|---------|-------------------------|
| `tickers`          | Space-separated tickers/CIKs                 | -       | `AAPL 0000320193`       |
| `-f`               | Path to file with tickers/CIKs               | -       | `-f input/ciks.txt`     |
| `-s`               | Output file path                             | `.env`  | `-s data/sec_trades.db` |
| `-d`               | Disable date combining for adjacent trades   | False   | `-d`                    |
| `-l`               | Max filings per ticker/CIK (-1 means no limit)| -1     | `-l 15`                 |
| `-a`, `--append`   | Append without deduplication                 | -       | `--append`              |
| `-r`, `--rewrite`  | Overwrite existing file                      | -       | `-r`                    |

#### **OpenInsider Scraper** (`openinsider_scraper.py`)
```bash
# Scrape tickers from CLI (e.g., Apple and Microsoft)
python openinsider_scraper.py AAPL MSFT -s oi_data.csv

# Scrape from a file using 8 parallel processes
python openinsider_scraper.py -f tickers.txt -s oi_data.db --processes 8
```

| Flag               | Description                          | Default | Example                   |
|--------------------|--------------------------------------|---------|---------------------------|
| `tickers`          | Space-separated tickers              | -       | `TSLA NVDA`               |
| `-f`               | Path to ticker file                  | -       | `-f input/tickers.txt`    |
| `-s`               | Output file path                     | `.env`  | `-s data/oi_trades.db`    |
| `-n`, `--processes`| Number of parallel processes         | 1       | `--processes 6`           |
| `-a`, `--append`   | Append without deduplication         | -       | `-a`                      |
| `-r`, `--rewrite`  | Overwrite existing file              | -       | `--rewrite`               |

---

### 2. Visualizing Data (`insider_data_visualizer.py`)
```bash
# Plot AAPL trades from 2023-01-01 to 2023-12-31 using scraped data
python insider_data_visualizer.py AAPL -sd 2023-01-01 -ed 2023-12-31 -s oi_data.csv
```

| Flag       | Description                          | Default                  | Example                   |
|------------|--------------------------------------|--------------------------|---------------------------|
| `ticker`   | Stock ticker symbol                  | -                        | `AAPL`                    |
| `-sd`      | Start date (YYYY-MM-DD)              | 1 year ago               | `-sd 2023-01-01`          |
| `-ed`      | End date (YYYY-MM-DD)                | Today                    | `-ed 2024-05-31`          |
| `-s`       | Scraped data file path               | `.env` value             | `-s merged_trades.csv`    |

---

## Configuration

### Environment Variables (`.env`)
| Variable          | Default       | Description                               |
|-------------------|---------------|-------------------------------------------|
| `LINK`            | `scrapes.csv` | Default output file path                  |
| `CSV_SEP`         | `;`           | CSV delimiter                             |
| `NUM_PROCESSES`   | `4`           | OpenInsider parallel processes            |
| `USER_AGENT`      | *Required*    | User agent for SEC requests (e.g., `"YourName/1.0 (your@email.com)"`) |
| `SEC_BET_REQ`     | `0.2`         | SEC request delay (seconds)               |

### Output Columns
All files include standardized columns:
- `X` (transaction type flag: `D` - derivative, `M` - multiple)
- `Filing Date`, `Trade Date`, `Ticker`, `Insider Name`, `Title`
- `Trade Type`, `Price`, `Qty`, `Value`, `FC` (SEC filing accession number or `NaN`)

---

## Project Structure

| File                          | Description                                      |
|-------------------------------|--------------------------------------------------|
| `arg_parser.py`               | CLI argument parsers for all scripts             |
| `base_scraper.py`             | Base class for data loading, cleaning, and saving|
| `SEC_insider_scraper.py`      | SEC Form-4 scraper                               |
| `openinsider_scraper.py`      | OpenInsider scraper with multiprocessing         |
| `insider_data_visualizer.py`  | Visualization script for trades and stock prices |
| `settings.py`                 | Loads environment variables and configurations   |

---

## Important Notes

- **SEC Compliance**: A valid `USER_AGENT` in your `.env` file is required to access SEC data. Use the format `"YourName/1.0 (your@email.com)"`.
- **Rate Limits**: The SEC enforces a rate limit of 10 requests per second. Increase the `SEC_BET_REQ` delay if you encounter rate limit errors.
- **Web Scraping Guidelines**: While OpenInsider’s terms of service allow temporary personal use downloads, and `ROBOTS.txt` only prohibits known SEO tools, please verify and adhere to the website’s policies before scraping.

---

## Acknowledgments

- **Data Sources**: 
  - [SEC Edgar](https://www.sec.gov/edgar)
  - [OpenInsider](http://openinsider.com/)



