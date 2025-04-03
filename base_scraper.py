import sqlite3
import pandas as pd
import logging
from pathlib import Path
from typing import List
from settings import CSV_SEP


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLUMNS = [
    'X', 'Filing Date', 'Trade Date', 'Ticker', 'Insider Name', 'Title',
    'Trade Type', 'Price', 'Qty', 'Value', 'FC'
]


class BaseScraper:
    def __init__(self, output_path: Path, save_mode: str):
        self.output_path = output_path
        self.save_mode = save_mode

    def _tickers_from_file(self, path: Path) -> List[str]:
        """Load tickers from text file"""
        if not path.exists():
            raise FileNotFoundError(f"Ticker file not found: {path}")

        with open(path, 'r') as f:
            return [line.strip() for line in f if line.strip()]

    def load_existing_data(self) -> pd.DataFrame:
        """Load existing scraped data and ensure consistent formatting"""
        if not self.output_path.exists():
            return pd.DataFrame(columns=COLUMNS)

        suffix = self.output_path.suffix.lower()

        try:
            if suffix == '.db':
                with sqlite3.connect(self.output_path) as conn:
                    df = pd.read_sql("SELECT * FROM transactions", conn)
            elif suffix == '.csv':
                df = pd.read_csv(self.output_path, sep=CSV_SEP)
            elif suffix == '.xlsx':
                df = pd.read_excel(self.output_path)
            else:
                raise ValueError(f"Unsupported format: {self.output_path.suffix}")

            # Ensure expected columns exist
            df = df.reindex(columns=COLUMNS, fill_value=pd.NA)

            if not df.empty:
                # Standardize data types
                df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').astype('Int64')
                df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
                df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
                df['Filing Date'] = pd.to_datetime(df['Filing Date'], errors='coerce')
                df['Trade Date'] = pd.to_datetime(df['Trade Date'], errors='coerce').dt.date

            return df

        except Exception as e:
            logger.error(f"Critical error loading {self.output_path}: {str(e)}")
            raise

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean duplicates from final dataframe"""
        return df.drop_duplicates(subset=[
            'Filing Date', 'Trade Date', 'Ticker', 'Insider Name',
            'Trade Type', 'Price', 'Qty', 'Value'
        ]).reset_index(drop=True)

    def save_results(self, df: pd.DataFrame):
        """Save results to configured output format"""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            # Prepare
            mode = 'w'
            mode_db = 'replace'
            if self.save_mode == 'append':
                mode = 'a'
                mode_db = 'append'

            if self.save_mode == 'merge':
                try:
                    existing_df = self.load_existing_data()
                except Exception as e:
                    logger.warning(f"Couldn't load existing data: {str(e)}")
                    existing_df = pd.DataFrame(columns=COLUMNS)

                df = pd.concat([existing_df, df], ignore_index=True)
                df = self._clean_data(df)

            # Save
            if self.output_path.suffix == '.csv':
                df.to_csv(self.output_path, mode=mode, index=False, sep=CSV_SEP)
            elif self.output_path.suffix == '.xlsx':
                with pd.ExcelWriter(self.output_path, engine='openpyxl', mode=mode) as writer:
                    df.to_excel(writer, index=False)
            elif self.output_path.suffix == '.db':
                with sqlite3.connect(self.output_path) as conn:
                    df.to_sql('transactions', conn, if_exists=mode_db, index=False)
            else:
                raise ValueError(f"Unsupported file format: {self.output_path.suffix}")

            verb = {'rewrite': 'Rewrote', 'append': 'Appended', 'merge': 'Merged'}[self.save_mode]
            logger.info(f"{verb} file with {len(df)} records to {self.output_path}")

        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
            raise