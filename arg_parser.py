import argparse

def get_sec_parser():
    parser = argparse.ArgumentParser(description='SEC Insider Trading Scraper')
    parser.add_argument('tickers', nargs='*', help='Ticker symbols or CIKs')
    parser.add_argument('-f', type=str, help='File with tickers/CIKs')
    parser.add_argument('-s', type=str, help='Output file path')
    parser.add_argument('-d', action='store_true', help='Disable date combining')
    parser.add_argument('-l', type=int, help='Filing limit per ticker')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--append', action='store_true',
                      help='Append new data without deduplication')
    group.add_argument('-r', '--rewrite', action='store_true',
                      help='Delete existing file and write fresh data')
    return parser

def get_openinsider_parser():
    parser = argparse.ArgumentParser(description='OpenInsider Scraper')
    parser.add_argument('tickers', nargs='*', help='Ticker symbols')
    parser.add_argument('-f', type=str, help='File with tickers')
    parser.add_argument('-s', type=str, help='Output file path')
    parser.add_argument('-n', '--processes', type=int, help='Number of processes to use')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--append', action='store_true',
                      help='Append new data without deduplication')
    group.add_argument('-r', '--rewrite', action='store_true',
                      help='Delete existing file and write fresh data')
    return parser

def get_visualizer_parser():
    parser = argparse.ArgumentParser(description='Trading Data Visualizer')
    parser.add_argument('ticker', type=str, help='Stock ticker symbol')
    parser.add_argument('-sd', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('-ed', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('-s', type=str, help='Scraped data file path')
    return parser