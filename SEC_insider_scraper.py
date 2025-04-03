import argparse
import time
import pandas as pd
import requests
import datetime as dt
import re
import logging
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict

from settings import SEC_REQUEST_DELAY, USER_AGENT, LINK
from arg_parser import get_sec_parser
from base_scraper import BaseScraper, COLUMNS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SECScraper(BaseScraper):
    def __init__(self, args: argparse.Namespace):
        self.args = args

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.last_request_time = dt.datetime.now()
        self.comb_adj_dates = not args.d
        self.filing_limit = args.l if args.l else -1

        # Initialize BaseScraper
        output_path = Path(args.s) if args.s else LINK
        save_mode = 'merge'
        if args.rewrite:
            save_mode = 'rewrite'
        elif args.append:
            save_mode = 'append'
        super().__init__(output_path, save_mode)

        self.ciks = self._process_input(args)

    def close_session(self):
        """Close requests session"""
        self.session.close()

    def _process_input(self, args: argparse.Namespace) -> List[str]:
        """Process input arguments to get list of CIKs"""
        ciks = []

        # Process file input
        if args.f:
            ciks += self._tickers_from_file(Path(args.f))

        # Process command line tickers
        if args.tickers:
            ciks += self._tickers_to_ciks(args.tickers)

        return list(set(ciks))  # Remove duplicates

    def _make_sec_request(self, url: str, retries: int = 3) -> requests.Response:
        """Make SEC request with rate limiting and retries"""
        for attempt in range(retries):
            elapsed = (dt.datetime.now() - self.last_request_time).total_seconds()
            if elapsed < SEC_REQUEST_DELAY:
                time.sleep(SEC_REQUEST_DELAY - elapsed)

            try:
                response = self.session.get(url, timeout=5)
                response.raise_for_status()

                if "Request Rate Threshold Exceeded" in response.text:
                    logger.error("SEC rate limit exceeded")
                    raise RuntimeError("SEC rate limit exceeded")

                self.last_request_time = dt.datetime.now()
                return response

            except requests.exceptions.HTTPError as e:
                if 500 <= e.response.status_code < 600 and attempt < retries - 1:  # Retry all server side errors
                    wait = 2 ** attempt
                    logger.warning(f"Retrying ({attempt + 1}/{retries}), {str(e)}")
                    time.sleep(wait)
                else:
                    logger.error(f"Request failed after {retries} retries: {str(e)}, {str(e)}")
                    raise

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < retries - 1:  # Retry network errors
                    wait = 2 ** attempt
                    logger.warning(f"Retrying ({attempt + 1}/{retries})")
                    time.sleep(wait)
                else:
                    logger.error(f"Network error after {retries} retries: {str(e)}")
                    raise

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {str(e)}")
                raise

    def _tickers_to_ciks(self, tickers: List[str]) -> List[str]:
        """Convert tickers to CIK numbers"""
        try:
            response = self._make_sec_request("https://www.sec.gov/files/company_tickers.json")
            cik_map = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch CIK map: {str(e)}")
            return []

        ciks = []
        for ticker in tickers:
            ticker = ticker.strip().upper()

            # Check if input is already a CIK
            if ticker.isdigit() and len(ticker) <= 10:
                ciks.append(ticker.zfill(10))
                continue

            # Search for ticker in SEC data
            found = False
            for entry in cik_map.values():
                if entry.get('ticker') == ticker:
                    ciks.append(str(entry['cik_str']).zfill(10))
                    found = True
                    break

            if not found:
                logger.warning(f"Could not find CIK for ticker: {ticker}")

        return ciks

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize insider name formatting"""
        words = []
        for word in name.split():
            if '-' in word:
                word = '-'.join([p.capitalize() for p in word.split('-')])
            else:
                word = word.capitalize()

            if word.lower().startswith('mc') and len(word) > 2:
                word = word[:2] + word[2].upper() + word[3:].lower()

            words.append(word)

        return ' '.join(words)

    @staticmethod
    def _custom_round(number: float, precision: int = 0) -> float:
        """Custom rounding function, rounding away from zero when the rounding part is exactly in the middle"""
        factor = 10 ** precision
        scaled = number * factor
        decimal = scaled - int(scaled)

        if abs(decimal) == 0.5:
            scaled = int(scaled) + (1 if scaled > 0 else -1)
        else:
            scaled = round(scaled)

        return (scaled / factor) if precision != 0 else int(scaled)

    def _combine_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """Combine transactions in the same filing occurring on adjacent or the same date"""
        # Grouping
        grouped = {}
        for trans in transactions:
            key = (trans['Trade Type'], trans['A_D'])
            if not self.comb_adj_dates:
                key += (trans['Trade Date'],)

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(trans)

        # Combining
        combined = []
        for key, group in grouped.items():
            total_qty = sum(t['Qty'] for t in group)
            total_value = sum(float(t['Price']) * abs(t['Qty']) for t in group)
            avg_price = total_value / abs(total_qty) if total_qty != 0 else 0

            combined.append({
                'X': group[0]['X'] + 'M' if len(group) > 1 else group[0]['X'],
                'Filing Date': group[0]['Filing Date'],
                'Trade Date': min(t['Trade Date'] for t in group),
                'Ticker': group[0]['Ticker'],
                'Insider Name': group[0]['Insider Name'],
                'Title': group[0]['Title'],
                'Trade Type': group[0]['Trade Type'],
                'Price': self._custom_round(avg_price, 2),
                'Qty': total_qty,
                'Value': int(self._custom_round(total_value)),
                'FC': group[0]['FC']
            })

        return combined

    def _process_filing(self, accession_number: str, cik: str) -> pd.DataFrame:
        """Process single SEC filing"""
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number.replace('-', '')}/{accession_number}.txt"

        try:
            response = self._make_sec_request(url)
            soup = BeautifulSoup(response.text, 'xml')
        except Exception as e:
            logger.warning(f"Failed to retrieve filing {accession_number}: {str(e)}")
            return pd.DataFrame()

        # Extract common filing information
        try:
            filing_data = {
                'X': 'D' if soup.find('derivativeTable') else '',
                'Filing Date': dt.datetime.strptime(
                    re.search(r"<ACCEPTANCE-DATETIME>(\d+)", response.text).group(1),
                    "%Y%m%d%H%M%S"
                ),
                'Ticker': soup.find('issuerTradingSymbol').text,
                'Insider Name': self._normalize_name(soup.find('rptOwnerName').text),
                'Title': self._extract_title(soup),
                'FC': accession_number
            }
        except AttributeError as e:
            logger.warning(f"Missing required filing data in {accession_number}: {str(e)}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error parsing {accession_number}: {str(e)}")
            return pd.DataFrame()

        # Process non-derivative transactions
        transactions = []
        for transaction in soup.find_all('nonDerivativeTransaction'):
            try:
                transactions.append(self._parse_transaction(transaction, filing_data))
            except Exception as e:
                logger.warning(f"Failed to parse non-derivative transaction: {str(e)}")

        # Process derivative transactions
        for transaction in soup.find_all('derivativeTransaction'):
            try:
                transactions.append(self._parse_transaction(transaction, filing_data))
            except Exception as e:
                logger.warning(f"Failed to parse derivative transaction: {str(e)}")

        if not transactions:
            return pd.DataFrame()

        return pd.DataFrame(self._combine_transactions(transactions))

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract and format insider title"""
        relationship = soup.find('reportingOwnerRelationship')
        title_parts = []

        if relationship.find('isOfficer', string=lambda x: x in ['true', '1']):
            title = relationship.find('officerTitle')
            title_text = title.string if title else 'See Remarks'
            if 'See Remarks' in title_text and soup.find('remarks'):
                title_text = soup.find('remarks').string
            title_parts.append(title_text)

        if relationship.find('isDirector', string=lambda x: x in ['true', '1']):
            title_parts.append('Director')

        if relationship.find('isTenPercentOwner', string=lambda x: x in ['true', '1']):
            title_parts.append('10% Owner')

        return ', '.join(title_parts) if title_parts else 'No Title'

    def _parse_transaction(self, transaction: BeautifulSoup, filing_data: Dict) -> Dict:
        """Parse individual transaction data"""
        try:
            price_elem = transaction.find('transactionPricePerShare')
            price = float(price_elem.value.text) if price_elem else 0.0
        except (AttributeError, ValueError):
            price = 0.0

        try:
            qty_elem = transaction.find('transactionShares')
            qty = int(qty_elem.value.text) if qty_elem else 0
        except (AttributeError, ValueError):
            qty = 0

        try:
            code = transaction.find('transactionAcquiredDisposedCode').value.text
        except AttributeError:
            code = ''

        return {
            **filing_data,
            'Trade Date': pd.to_datetime(transaction.find('transactionDate').value.text).date(),
            'Trade Type': self._trade_type(transaction.find('transactionCode').text),
            'Price': price,
            'Qty': qty * (-1 if code == 'D' else 1),
            'A_D': code
        }

    @staticmethod
    def _trade_type(code: str) -> str:
        """Map transaction codes to openinsider format"""
        types = {
            'P': 'Purchase',
            'S': 'Sale',
            'A': 'Grant',
            'D': 'Sale to Iss',
            'G': 'Gift',
            'F': 'Tax',
            'M': 'OptEx',
            'X': 'OptEx',
            'C': 'Cnv Deriv',
            'W': 'Inherited'
        }
        return f"{code} - {types.get(code, 'Unknown')}"

    def _get_filings(self, cik: str) -> List[str]:
        """Retrieve list of Form 4 filings for a CIK"""
        try:
            response = self._make_sec_request(f"https://data.sec.gov/submissions/CIK{cik}.json")
            data = response.json()
            return [
                acc for acc, form in zip(
                    data['filings']['recent']['accessionNumber'],
                    data['filings']['recent']['form']
                ) if form == '4'
            ]
        except Exception as e:
            logger.error(f"Failed to get filings for CIK {cik}: {str(e)}")
            return []

    def _process_cik_filings(self, cik: str, accession_numbers: List[str]) -> pd.DataFrame:
        """Processe all filings for a single CIK"""
        df = pd.DataFrame(columns=COLUMNS)
        for i, accession_number in enumerate(accession_numbers):
            if self.filing_limit != -1 and i >= self.filing_limit:
                break
            try:
                df = pd.concat([df, self._process_filing(accession_number, cik)])
            except Exception as e:
                logger.warning(f"Skipping filing {accession_number}: {str(e)}")
        return df

    def scrape(self) -> pd.DataFrame:
        """Main scraping controller"""
        df = pd.DataFrame(columns=COLUMNS)

        for cik in self.ciks:
            try:
                logger.info(f"Processing CIK: {cik}")
                filings = self._get_filings(cik)
                data = self._process_cik_filings(cik, filings)
                df = pd.concat([df, data])
            except Exception as e:
                logger.error(f"Failed to process CIK {cik}: {str(e)}")

        return df


def main():
    parser = get_sec_parser()
    args = parser.parse_args()

    try:
        scraper = SECScraper(args)
        df = scraper.scrape()
        scraper.save_results(df)
        logger.info("Scraping completed successfully")
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        exit(1)
    finally:
        if scraper:
            scraper.close()


if __name__ == "__main__":
    main()
