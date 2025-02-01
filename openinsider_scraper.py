# file structure:
# X; Filing Date; Trade Date; Ticker; Insider Name; Title; Trade Type; Price; Quantity; Value;

import pandas as pd
import math
import multiprocessing as mp
from pathlib import Path
import sqlite3
import argparse
import os
from dotenv import load_dotenv

columns = [  # openinsider column names
    'X', 'Filing Date', 'Trade Date', 'Ticker', 'Insider Name', 'Title', 'Trade Type',
    'Price', 'Qty', 'Owned', 'deltaOwn', 'Value',
    '1d', '1w', '1m', '6m'
]

def str_to_bool(str):
    if str == "True":
        return True
    return False

## ENV VARIABLES ##

load_dotenv()

script_dir = Path(__file__).resolve().parent  # path to parent folder of the script

link = script_dir / os.getenv("LINK", "scrapes.csv")  # link to file with scraped data - can be any of the following types: '.csv', '.txt', '.xlsx', '.db'

csv_sep = os.getenv("CSV_SEP", ';')  # separator in case link is .csv or .txt file

default_ticker_link = script_dir / os.getenv("TICKER_LINK", "default_tickers.txt")  # link to txt with default ticker list

num_processes = int(os.getenv("NUM_PROCESSES", '4'))  # number of processes

remove_OE = str_to_bool(os.getenv("REMOVE_OE", "False"))


#######


def Strip_array(vec):  # strips every ticker in an array from white characters
    return [string.strip() for string in vec]


def split_into_sublists(list, parts_num):  # splits list into parts
    chunk_size = math.ceil(len(list) / parts_num)
    return [list[i:i+chunk_size] for i in range(0, len(list), chunk_size)]


def tickers_from_file(path):  # takes file path and outputs list of tickers in that file
    if not (Path(path).exists() and path.endswith(".txt")):
        print(f"file {path} doesn't exist or is not a txt file")
        exit()

    stocklist = open(path, "r")
    tickers = stocklist.readlines()
    stocklist.close()
    return Strip_array(tickers)


def scrape_page(ticker):
    # openinsider url to data with specific ticker
    url = "http://openinsider.com/screener?s=" + ticker + \
          "&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&xa=1&xd=1&xg=1&xf=1&xm=1&xx=1&xc=1&xw=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1"
    try:
        page = requests.get(url, timeout=10)
    except:
        print(f"can't scrape {ticker}")  # if requests doesnt work
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

    print(f"Successfully scrapped data about {ticker} insiders")

    return rows


def worker(tickers):
    df = pd.DataFrame(columns=columns)  # data frame with craped data

    for ticker in tickers:
        rows = scrape_page(ticker)
        df = pd.concat([df, pd.DataFrame(rows, columns = columns)], ignore_index=True)  # adding rows about this ticker to df

    df = df.drop(['Owned', 'deltaOwn', '1d', '1w', '1m', '6m'], axis=1)  # drop columns with not usefoul rows

    # Changing fields to better suit our needs
    if csv_sep == ',':
        df['Title'] = df['Title'].str.replace(',', ';')
    elif csv_sep == ';':
        df['Title'] = df['Title'].str.replace(';', ',')
    df["Value"] = df["Value"].str.replace(r'[+$,]', '', regex=True)
    df['Price'] = df['Price'].str.replace('$', '')
    df['Qty'] = df['Qty'].str.replace(r'[+,]', '', regex=True)
    if remove_OE == True:
        df['Trade Type'] = df['Trade Type'].str.replace('+OE', '')

    return df




if __name__ == "__main__":

    tickers = []  # list with tickers to scrape

    parser = argparse.ArgumentParser(description="")

    # Add argparse options for -a, -b, -c (and similar options)
    parser.add_argument('-f', type=str, help="Provide file with tickers")
    parser.add_argument('-s', type=str, help="Provide file with scrapes")
    parser.add_argument('-o', action='store_true', help="Remove +OE")

    # Use `parse_known_args()` to allow argparse to handle the first few arguments
    args, unknown = parser.parse_known_args()

    if args.f is not None:
        tickers = tickers_from_file(args.f)
    if args.s is not None:
        link = args.s
    if args.o:
        remove_OE = True

    tickers += unknown

    tickers = [ticker.upper() for ticker in tickers]  # change all tickers to upper case characters


    while len(tickers) < 20 * num_processes and num_processes > 1:  # if the number of tickers is small use smaller number of threads
        num_processes //= 2

    # read data already scraped in csv
    df = pd.DataFrame(columns = [  # dataframe column names
    'X', 'Filing Date', 'Trade Date', 'Ticker', 'Insider Name', 'Title', 'Trade Type',
    'Price', 'Qty', 'Value'])

    try:
        if(link.suffix in ['.csv', '.txt']):
            df = pd.read_csv(link, sep = csv_sep, dtype=str, na_filter=False)
        elif(link.suffix == '.xlsx'):
            df = pd.read_excel(link, index_col=0, dtype=str, keep_default_na=False)
        elif(link.suffix == '.db'):
            conn = sqlite3.connect(link)
            df = pd.read_sql_query("SELECT * FROM people", conn)
        else:
            print("unsuported database file format")
            exit()
    except:
        pass


    # scrape openinsider using multithreading and add resutls to df
    with mp.Pool(processes = num_processes) as pool:
        results = pool.imap_unordered(worker, split_into_sublists(tickers, num_processes))

        for result in results:
            df = pd.concat([df, result], ignore_index=False)

    # drop duplicates, there might have been data already in file that we scraped once again
    df = df.drop_duplicates(subset = ['Filing Date', 'Trade Date', 'Ticker', 'Insider Name', 'Trade Type',
        'Price', 'Qty', 'Value'])

    # save and print data
    if(link.suffix in ['.csv', '.txt']):
        df.to_csv(link, sep = csv_sep, index=False)
    elif(link.suffix == '.xlsx'):
        df.to_excel(link)
    else:  # if suffix == '.db'
        conn = sqlite3.connect(link)
        df.to_sql('people', conn, if_exists='replace', index=False)
        conn.close()
    print(df)



