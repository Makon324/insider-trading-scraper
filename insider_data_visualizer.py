from typing import Tuple, List
import logging
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.dates import DateFormatter
import seaborn as sns
from adjustText import adjust_text
from datetime import datetime, timedelta
import argparse


from arg_parser import get_visualizer_parser
from base_scraper import BaseScraper
from settings import LINK, CSV_SEP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Visualizer:
    def __init__(self, args: argparse.Namespace):
        self.ticker = args.ticker
        self.start_date = self._parse_date(args.sd, default=datetime.now() - timedelta(days=365))
        self.end_date = self._parse_date(args.ed, default=datetime.now())
        self.data_path = Path(args.s) if args.s else LINK
        self.df = self._load_data()

    @staticmethod
    def _parse_date(date_str: str, default: datetime) -> datetime:
        """Parse date string or return default"""
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError as e:
                logger.warning(f"Invalid date format: {date_str}. Using default.")
        return default

    def _load_data(self) -> pd.DataFrame:
        """Load data using BaseScraper and return only Buys and Sells"""
        scraper = BaseScraper(output_path=self.data_path, save_mode="rewrite")

        try:
            df = scraper.load_existing_data()
        except Exception as e:
            logger.error(f"Failed to load data: {str(e)}")
            raise

        # Apply filters
        df = df[df["Ticker"] == self.ticker]
        df = df[df["Trade Type"].isin(["P - Purchase", "S - Sale"])]
        df = df[
            (df["Filing Date"] >= pd.to_datetime(self.start_date)) &
            (df["Filing Date"] <= pd.to_datetime(self.end_date))
            ]
        return df.sort_values(by=["Filing Date", "Trade Date"], ascending=[True, False])

    def _generate_labels(self) -> Tuple[List[str], List[datetime]]:
        """Generate annotation labels"""
        labels = []
        labels_dates = []
        current_date = datetime.min

        for _, row in self.df.iterrows():
            if row["Filing Date"].date() != current_date.date():
                current_date = row["Filing Date"]
                labels.append(f"Date: {current_date}")
                labels_dates.append(current_date)
            else:
                labels[-1] += "\n----------------------\n" + f"Date: {current_date}"

            labels[-1] += (
                f"\n----------------------\n" 
                f"TD: {row['Trade Date']}\n"  # Fixed line
                f"TT: {row['Trade Type']}\n"
                f"IN: {row['Insider Name']}\n"
                f"T: {row['Title']}\n"
                f"P: {row['Price']} Qty: {row['Qty']}"
            )

        return labels, labels_dates

    def _fetch_stock_data(self) -> pd.DataFrame:
        """Fetch stock data using yfinance"""
        try:
            data = yf.download(self.ticker, start=self.start_date, end=self.end_date, auto_adjust=True)

            if data.empty:
                logging.warning(f"No data available for {self.ticker} between {self.start_date} and {self.end_date}.")
                return pd.DataFrame()

            return data

        except Exception as e:
            logging.error(f"Error fetching data for {self.ticker} using yfinance: {e}")

        return pd.DataFrame()

    def visualize(self):
        """Main visualization controller"""
        if self.df.empty:
            logger.warning("No data to visualize")
            return

        # Fetch stock data
        stock_data = self._fetch_stock_data()
        if stock_data.empty:
            return

        plt.figure(figsize=(12, 6))
        try:
            # Reset index and plot
            stock_data_reset = stock_data.reset_index()
            sns.lineplot(
                x=stock_data_reset['Date'],  # Use explicit 1D array
                y=stock_data_reset['Close'].values.flatten(),  # Force 1D
                label=f'{self.ticker} Close Price',
                color='blue'
            )
        except Exception as e:
            logger.error(f"Plotting failed: {str(e)}")
            return

        # Generate annotations
        labels, labels_dates = self._generate_labels()
        if not labels or not labels_dates:
            logger.warning("No insider trades to annotate")
            return

        texts = []
        for label, date in zip(labels, labels_dates):
            # Find nearest index using stock_data_reset's 'Date' column
            nearest_idx = stock_data_reset['Date'].sub(date).abs().idxmin()
            close_prices = stock_data_reset['Close'].to_numpy().flatten()  # 1D array
            if nearest_idx >= len(close_prices):
                logger.error(f"Index {nearest_idx} out of bounds. Skipping annotation.")
                continue
            price = close_prices[nearest_idx].item()  # Ensure scalar

            color = 'green' if 'P - Purchase' in label else 'red'
            text = plt.annotate(
                label,
                xy=(date, price),
                xytext=(date, price * (0.7 + 0.5 * (len(texts) % 2))),
                arrowprops=dict(facecolor='black', arrowstyle='->'),
                fontsize=6,
                bbox=dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.7)
            )
            texts.append(text)

        adjust_text(texts, verbose=False)
        plt.title(f"{self.ticker} Stock Prices with Insider Trades")
        plt.xlabel("Date")
        plt.ylabel("Close Price (USD)")
        plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.show()


def main():
    parser = get_visualizer_parser()
    args = parser.parse_args()

    try:
        visualizer = Visualizer(args)
        visualizer.visualize()
        logger.info("Visualization completed")
    except Exception as e:
        logger.error(f"Visualization failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()