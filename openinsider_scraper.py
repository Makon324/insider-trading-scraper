import argparse
import math
import multiprocessing as mp
import pandas as pd
import numpy as np
import requests
import logging
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional

from arg_parser import get_openinsider_parser
from base_scraper import BaseScraper, COLUMNS
from settings import NUM_PROCESSES, USER_AGENT, CSV_SEP, LINK

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

columns_op = [  # openinsider column names
    'X', 'Filing Date', 'Trade Date', 'Ticker', 'Insider Name', 'Title', 'Trade Type',
    'Price', 'Qty', 'Owned', 'deltaOwn', 'Value',
    '1d', '1w', '1m', '6m'
]


class OpenInsiderScraper(BaseScraper):
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.tickers = self._process_input(args)
        self.num_processes = args.processes or NUM_PROCESSES

        # Initialize BaseScraper
        output_path = Path(args.s) if args.s else LINK
        save_mode = 'merge'
        if args.rewrite:
            save_mode = 'rewrite'
        elif args.append:
            save_mode = 'append'
        super().__init__(output_path, save_mode)

    def _process_input(self, args: argparse.Namespace) -> List[str]:
        """Process input arguments to get list of tickers"""
        tickers = []

        if args.f:
            tickers += self._tickers_from_file(Path(args.f))

        if args.tickers:
            tickers += [t.upper().strip() for t in args.tickers]

        return list(set(tickers))

    @staticmethod
    def _split_into_chunks(lst: List, n_chunks: int) -> List[List]:
        """Split list into equal chunks"""
        chunk_size = math.ceil(len(lst) / n_chunks)
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

    @staticmethod
    def _scrape_page(ticker: str) -> pd.DataFrame:
        """Scrape individual ticker page"""
        url = "http://openinsider.com/screener?s=" + ticker + \
              "&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&xa=1&xd=1&xg=1&xf=1&xm=1&xx=1&xc=1&xw=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1"
        try:
            page = session.get(url, timeout=10)
            page.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to scrape {ticker}: {str(e)}")
            return []

        HTML = BeautifulSoup(page.text, "html.parser")

        if len(HTML.find_all("tbody")) <= 1:  # if theres no querry
            print("No insider trading data found for " + ticker)
            return []

        table = HTML.find_all("tbody")[1]  # table in html

        rows = []  # data frame with data about this ticker
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            rows.append(cols)

        logger.info(f"Scraped {len(rows)} transactions for {ticker}")
        return OpenInsiderScraper._clean_rows(rows)

    @staticmethod
    def _clean_rows(rows: List[List]) -> pd.DataFrame:
        """Clean scraped rows and ensure standardized data types"""
        df = pd.DataFrame(rows, columns=columns_op)
        df['FC'] = np.nan
        final_df = df.drop(columns=df.columns_op.difference(COLUMNS)).copy()

        # Clean text formatting
        if CSV_SEP == ',':
            final_df['Title'] = final_df['Title'].str.replace(',', ';')
        elif CSV_SEP == ';':
            final_df['Title'] = final_df['Title'].str.replace(';', ',')

        # Remove symbols and convert to numeric
        final_df["Value"] = pd.to_numeric(
            final_df["Value"].str.replace(r'[+$,]', '', regex=True),
            errors='coerce'
        )
        final_df['Price'] = pd.to_numeric(
            final_df['Price'].str.replace('$', ''),
            errors='coerce'
        )
        final_df['Qty'] = pd.to_numeric(
            final_df['Qty'].str.replace(r'[+,]', '', regex=True),
            errors='coerce'
        ).astype('Int64')  # Nullable integer type

        # Convert dates to datetime objects
        final_df['Filing Date'] = pd.to_datetime(
            final_df['Filing Date'], errors='coerce'
        )
        final_df['Trade Date'] = pd.to_datetime(
            final_df['Trade Date'], errors='coerce'
        ).dt.date  # Match existing data's date format

        return final_df

    def _worker(self, tickers: List[str]) -> pd.DataFrame:
        """Process a chunk of tickers (worker function)"""
        df = pd.DataFrame(columns=columns_op)
        with requests.Session() as session:
            session.headers.update(USER_AGENT)
            for ticker in tickers:
                ticker_df = self._scrape_page(ticker, session)
                df = pd.concat([df, ticker_df], ignore_index=True)

        return df

    def scrape(self) -> pd.DataFrame:
        """Main scraping controller"""
        if not self.tickers:
            logger.warning("No tickers provided for scraping")
            return pd.DataFrame()

        # Adjust process count based on workload
        while len(self.tickers) < 20 * self.num_processes and self.num_processes > 1:
            self.num_processes //= 2

        chunks = self._split_into_chunks(self.tickers, self.num_processes)

        logger.info(f"Scraping {len(self.tickers)} tickers using {self.num_processes} processes")

        with mp.Pool(processes=self.num_processes) as pool:
            results = pool.imap_unordered(self._worker, chunks)
            final_df = pd.concat(results, ignore_index=True)

        return final_df


def main():
    parser = get_openinsider_parser()
    args = parser.parse_args()

    try:
        scraper = OpenInsiderScraper(args)
        df = scraper.scrape()
        scraper.save_results(df)
        logger.info("Scraping completed successfully")
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()