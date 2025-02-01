# Insider Trading Data Scraper & Visualizer

A Python-based tool to scrape insider trading data from **OpenInsider** and **SEC Form-4 filings**, then visualize it alongside stock price trends.

## Features

- **Dual Scraping Sources**
  - **OpenInsider Scraper**: Fetches insider trading data from [openinsider.com](http://openinsider.com/).
  - **SEC Scraper**: Retrieves Form-4 filings from the SEC Edgar database.
- **Data Storage**: Supports CSV, Excel, TXT, and SQLite databases.
- **Visualization**: Generates annotated stock price charts with insider trade details (purchases/sales) using `yfinance` and `seaborn`.
- **Multi-Processing**: OpenInsider scraper uses multiprocessing for faster data collection.
- **Customizable**: Configure file paths, date ranges, and data filters via CLI or `.env` file.

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/insider-trading-analysis.git
   cd insider-trading-analysis
   ```

2. **Install Dependencies**
   ```bash
   pip install pandas yfinance matplotlib seaborn requests beautifulsoup4 python-dotenv adjustText
   ```

## Usage

### 1. Scraping Data

#### **OpenInsider Scraper** (`openinsider_scraper.py`)
- **Scrape Tickers from CLI**:
  ```bash
  python openinsider_scraper.py AAPL MSFT -s scrapes.csv
  ```
- **Scrape Tickers from a File**:
  ```bash
  python openinsider_scraper.py -f tickers.txt -s scrapes.csv
  ```
  - `-f`: Path to a `.txt` file containing tickers (one per line).
  - `-s`: Output file (e.g., `scrapes.csv`).
  - `-o`: Remove "+OE" from trade types.

#### **SEC Scraper** (`SEC_insider_scraper.py`)
- **Scrape by Ticker or CIK**:
  ```bash
  python SEC_insider_scraper.py AAPL 0000320193 -s sec_scrapes.csv
  ```
  - `-f`: Path to a `.txt` file containing tickers/CIKs.
  - `-s`: Output file.
  - `-d`: Disable combining adjacent trade dates.
  - `-l`: Limit filings per ticker (e.g., `-l 10`).

### 2. Visualizing Data (`insider_data_visualizer.py`)
Generate a stock price chart with insider trade annotations:
```bash
python insider_data_visualizer.py AAPL -sd 2023-01-01 -ed 2023-12-31 -s scrapes.csv
```
- `-sd`: Start date (default: 1 year ago).
- `-ed`: End date (default: today).
- `-s`: Path to scraped data file.

**Output**: Interactive plot with:
- Stock price trend.
- Annotations for insider trades (date, type, insider name, price, quantity).

---

## Configuration

1. **Environment Variables** (`.env`)
   ```ini
   LINK=scrapes.csv       # Path to data file
   CSV_SEP=;              # CSV separator
   TICKER_LINK=tickers.txt # Default ticker list
   NUM_PROCESSES=4        # OpenInsider multiprocessing
   USER_AGENT=YourName/1.0 # SEC scraper user agent
   SEC_BET_REQ=0.2        # SEC request delay (seconds)
   ```

2. **File Formats**
   - Use `.csv`, `.xlsx`, `.txt`, or `.db` (SQLite) for input/output.

---

## Example Workflow

1. **Scrape Data from OpenInsider**
   ```bash
   python openinsider_scraper.py TSLA -s scrapes.csv
   ```

2. **Visualize**
   ```bash
   python insider_data_visualizer.py TSLA -sd 2023-01-01 -s scrapes.csv
   ```

---

## Notes

- **SEC Rate Limits**: The SEC enforces a rate limit (10 requests/second). Adjust `SEC_BET_REQ` in `.env` if needed.
- **User Agent**: Set a valid `USER_AGENT` in `.env` to avoid blocking by the SEC.
- **Data Cleaning**: Duplicate entries are automatically removed during scraping.


