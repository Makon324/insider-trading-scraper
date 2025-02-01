# -f  -  ticker list in file
# -d  -  combine adj dates = False
# -s  -  file with scrapes
# -l  -  filing limit per ticker | -1 - no limit

from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
from datetime import datetime, timedelta
import datetime as dt
import time
from pathlib import Path
import sqlite3
import argparse
import os
from dotenv import load_dotenv


columns = [  # dataframe column names
    'X', 'Filing Date', 'Trade Date', 'Ticker', 'Insider Name', 'Title', 'Trade Type',
    'Price', 'Qty', 'Value'
]

def str_to_bool(str):
    if str == "True":
        return True
    return False

## ENV VARIABLES ##

load_dotenv()

script_dir = Path(__file__).resolve().parent  # path to parent folder of the script

link = script_dir / os.getenv("LINK",
                              "scrapes.csv")  # link to file with scraped data - can be any of the following types: '.csv', '.txt', '.xlsx', '.db'

csv_sep = os.getenv("CSV_SEP", ';')  # separator in case link is .csv or .txt file

default_ticker_link = script_dir / os.getenv("TICKER_LINK", "default_tickers.txt")  # link to txt with default ticker list

seconds_between_requests = float(os.getenv("SEC_BET_REQ", 0.2))

filing_limit_per_ticker = int(os.getenv("FIL_LIM_PTIC", -1))  # default max number of filings, if -1 then there is no limit

comb_adj_dates = str_to_bool(os.getenv("COMB_ADJ_DATES", "True"))

headers = {
    'User-Agent': os.getenv("USER_AGENT", '')
}

#######


def SEC_request(url):
    # waiting, so that 10 req / s wouldnt be met
    seconds_since_last = (dt.datetime.now() - SEC_request.timenow).total_seconds()
    seconds_to_wait = seconds_between_requests - seconds_since_last
    if seconds_to_wait > 0:
        time.sleep(seconds_to_wait)
    SEC_request.timenow = dt.datetime.now()

    response = requests.get(url, headers=headers)
    if "<title>SEC.gov | Request Rate Threshold Exceeded</title>" in response.text.split('\n')[:10]:  # checking first 10 lines for response for too much SEC requests
        print("Too many SEC requests")
        exit()
    else:
        return response

SEC_request.timenow = dt.datetime.now()


def Strip_array(vec):  # strips every ticker in an array from white characters
    return [string.strip() for string in vec]

def normalize_Name(name):
    # Split the string into words by spaces, then process each word
    words = name.split(' ')
    capitalized_words = []
    for word in words:
        # If a word contains a hyphen, split and capitalize sub-words
        if '-' in word:
            subwords = word.split('-')
            capitalized_word = '-'.join(subword.capitalize() for subword in subwords)
        else:
            capitalized_word = word.capitalize()
        capitalized_words.append(capitalized_word)
    # Join the capitalized words back with spaces
    name = ' '.join(capitalized_words)

    if 'Mc' in name:
        index = name.index('Mc') + 2  # Find the letter after 'Mc'
        if index < len(name):  # Ensure the next letter exists
            name = name[:index] + name[index].upper() + name[index + 1:]

    return name

def custom_round(n, precision=0):
    # Calculate the factor to scale the number based on precision
    factor = 10 ** precision
    # Scale the number to avoid rounding issues
    n_scaled = n * factor

    # Handle .5 rounding behavior
    if n_scaled % 1 == 0.5 or n_scaled % 1 == -0.5:  # Handles both positive and negative numbers
        n_scaled = int(n_scaled) + (1 if n_scaled > 0 else -1)
    else:
        n_scaled = round(n_scaled)

    # Scale back the number to the original precision
    result = n_scaled / factor

    # Return an integer if precision is 0
    return int(result) if precision == 0 else result

def tickers_to_CIKs(tickers):
    data_JSON = SEC_request(r"https://www.sec.gov/files/company_tickers.json").json()

    for i in range(len(tickers)):
        org = tickers[i]
        if tickers[i].isalpha():
            tickers[i] = tickers[i].upper()
            for key, value in data_JSON.items():
                if value.get('ticker') == tickers[i]:
                    tickers[i] = str(value.get('cik_str'))

        tickers[i] = tickers[i].zfill(10)

        if not tickers[i].isnumeric():
            print(f"{org} in neither ticker or CIK")
            exit()
        if len(tickers[i]) > 10:
            print(f"CIK should contain at most 10 numbers: {org}")
            exit()

    return tickers


def tickers_from_file(path):  # takes file path and outputs list of tickers in that file
    if not (Path(path).exists() and path.endswith(".txt")):
        print(f"file {path} doesn't exist or is not a txt file")
        exit()

    stocklist = open(path, "r")
    tickers = stocklist.readlines()
    stocklist.close()
    return Strip_array(tickers)



def trade_type(type):
    if type == 'P':
        return 'P - Purchase'
    elif type == 'S':
        return 'S - Sale'
    elif type == 'A':
        return 'A - Grant'
    elif type == 'D':
        return 'D - Sale to Iss'
    elif type == 'G':
        return 'G - Gift'
    elif type == 'F':
        return 'F - Tax'
    elif type == 'M':
        return 'M - OptEx'
    elif type == 'X':
        return 'X - OptEx'
    elif type == 'C':
        return 'C - Cnv Deriv'
    elif type == 'W':
        return 'W - Inherited'
    else:
        return ''


def combine_by_trans(trans_list):
    wyn_list = []
    already_listed = []
    for el in trans_list:
        if comb_adj_dates == False:
            trade_dates = datetime.strptime(el["Trade Date"], "%Y-%m-%d")
            if not (el["Trade Type"], el["Trade Date"], el["A_D"]) in already_listed:
                already_listed.append((el["Trade Type"], el["Trade Date"], el["A_D"]))
                _PPS = 0
                totqty = 0
                tottrans = 0
                for row in trans_list:
                    if (row["Trade Type"], row["Trade Date"], row["A_D"]) == (el["Trade Type"], el["Trade Date"], el["A_D"]):
                        tottrans += 1
                        _PPS += float(row["Price"]) * row["Qty"]
                        totqty += int(row["Qty"])

                _X_ = ''
                if tottrans > 1:
                    _X_ = 'M'

                if comb_adj_dates and len(trade_dates) > 1:
                    combined_trade_date = min(trade_dates).strftime("%Y-%m-%d")
                else:
                    combined_trade_date = el["Trade Date"]

                transaction_data = {
                    "X": el["X"] + _X_,
                    "Filing Date": el["Filing Date"],
                    "Trade Date": combined_trade_date,
                    "Ticker": el["Ticker"],
                    "Insider Name": el["Insider Name"],
                    "Title": el["Title"],
                    "Trade Type": el["Trade Type"],
                    "Price": "{:.2f}".format(custom_round(_PPS / totqty, 2)),
                    "Qty": str(totqty),
                    "Value": str(custom_round(_PPS)),
                    "FC": el["FC"]
                }

                wyn_list.append(transaction_data)


        else:
            if not (el["Trade Type"], el["A_D"]) in already_listed:
                already_listed.append((el["Trade Type"], el["A_D"]))
                _PPS = 0
                totqty = 0
                tottrans = 0
                trade_dates = []
                for row in trans_list:
                    if (row["Trade Type"], row["A_D"]) == (el["Trade Type"], el["A_D"]):
                        trade_dates.append(datetime.strptime(row["Trade Date"], "%Y-%m-%d"))
                        tottrans += 1
                        _PPS += float(row["Price"]) * row["Qty"]
                        totqty += int(row["Qty"])

                _X_ = ''
                if tottrans > 1:
                    _X_ = 'M'

                if comb_adj_dates and len(trade_dates) > 1:
                    combined_trade_date = min(trade_dates).strftime("%Y-%m-%d")
                else:
                    combined_trade_date = el["Trade Date"]

                transaction_data = {
                    "X": el["X"] + _X_,
                    "Filing Date": el["Filing Date"],
                    "Trade Date": combined_trade_date,
                    "Ticker": el["Ticker"],
                    "Insider Name": el["Insider Name"],
                    "Title": el["Title"],
                    "Trade Type": el["Trade Type"],
                    "Price": "{:.2f}".format(custom_round(_PPS / totqty, 2)),
                    "Qty": str(totqty),
                    "Value": str(custom_round(_PPS)),
                    "FC": el["FC"]
                }

                wyn_list.append(transaction_data)


    return wyn_list



def get_filings(cik):
    url = f'https://data.sec.gov/submissions/CIK{cik}.json'

    response = SEC_request(url)

    data = response.json()

    dl = len(data["filings"]["recent"]["form"])

    wyn = []

    for i in range(dl):
        if data["filings"]["recent"]["form"][i] == "4":
            wyn.append(data["filings"]["recent"]["accessionNumber"][i])

    return wyn

def get_trade(accNum, cik):
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accNum.replace('-', '')}/{accNum}.txt"

    response = SEC_request(url)

    HTML = response.text

    soup = BeautifulSoup(HTML, 'xml')

    if soup.derivativeTable:
        _X_ = 'D'
    else:
        _X_ = ''

# finding if nonDeriviative transactions are present
    transactions = soup.find_all('nonDerivativeTransaction')
    if transactions == []:
        return pd.DataFrame(columns = columns)

# getting acceptance date
    acceptance_datetime_match = re.search(r"<ACCEPTANCE-DATETIME>(\d+)", HTML)

    acceptance_datetime = acceptance_datetime_match.group(1) if acceptance_datetime_match else None

    formatted_date = datetime.strptime(acceptance_datetime, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")

# getting everything else thats constant for the whole filing
    ticker = soup.find('issuerTradingSymbol').text
    insider_name = soup.find('rptOwnerName').text

# getting insider title
    insider_title = ''
    ownrel = soup.find('reportingOwnerRelationship')

    if ownrel.find('isOfficer'):
        if ownrel.find('isOfficer').text in ['true', '1']:
            if 'See Remarks' in ownrel.find('officerTitle').text and soup.find('remarks'):
                insider_title = soup.find('remarks').text
            else:
                insider_title = ownrel.find('officerTitle').text

    if ownrel.find('isDirector') and insider_title == '':
        if ownrel.find('isDirector').text in ['true', '1']:
            insider_title = "Dir"

    if ownrel.find('isTenPercentOwner'):
        if ownrel.find('isTenPercentOwner').text in ['true', '1']:
            insider_title += ", 10%"

    insider_title = insider_title.lstrip(", ")
    if insider_title == '':
        insider_title = 'No title'

# getting data about individual trades
    transaction_list = []

    for transaction in transactions:

        # getting Price Per Share and Qty
        try:
            PPS = transaction.find('transactionPricePerShare').value.text
        except:
            PPS = '0'
        qty = transaction.find('transactionShares').value.text

        # getting A/D code
        if transaction.find('transactionAcquiredDisposedCode').value.text == 'D':
            acc_dis = -1
        else:
            acc_dis = 1

        transaction_data = {
            "X": _X_,
            "Filing Date": formatted_date,
            "Trade Date": transaction.find('transactionDate').value.text,
            "Ticker": ticker,
            "Insider Name": normalize_Name(insider_name),
            "Title": insider_title,
            "Trade Type": trade_type(transaction.find('transactionCode').text),
            "Price": PPS,
            "Qty": int(qty) * acc_dis,  # integer
            "Value": str(custom_round(int(qty)*float(PPS)*acc_dis)),
            "A_D": acc_dis,  # temporary to signal wheter transaction accuired or disposed shares
            "FC": accNum
        }

        transaction_list.append(transaction_data)

    transaction_list = combine_by_trans(transaction_list)

    df = pd.DataFrame(transaction_list)

    return df


def scrape_CIK(CIK):
    filings = get_filings(CIK)
    df = pd.DataFrame(columns = columns)
    i = 0
    for filing in filings:
        if i >= filing_limit_per_ticker and filing_limit_per_ticker != -1:
            break
        print(filing)
        new_row = get_trade(filing, CIK)
        df = pd.concat([df, new_row], ignore_index=True)
        i += 1
    return df


if __name__ == "__main__":

    CIKs = []  # list with CIKs to scrape

    parser = argparse.ArgumentParser(description="")

    # Add argparse options for -a, -b, -c (and similar options)
    parser.add_argument('-f', type=str, help="Provide file with tickers")
    parser.add_argument('-s', type=str, help="Provide file with scrapes")
    parser.add_argument('-d', action='store_true', help="Disable comb. adj. dates")
    parser.add_argument('-l', type=int, help="Provide limit to number of filings per ticker (-1 for no limit)")

    # Use `parse_known_args()` to allow argparse to handle the first few arguments
    args, unknown = parser.parse_known_args()

    if args.f is not None:
        CIKs = tickers_from_file(args.f)
    if args.s is not None:
        link = args.s
    if args.d:
        comb_adj_dates = False
    if args.l is not None:
        filing_limit_per_ticker = args.l

    CIKs += tickers_to_CIKs(unknown)

    CIKs = tickers_to_CIKs(CIKs)

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

    # scrape SEC website form-4 filings about given CIKs and add results to df
    for CIK in CIKs:
        result = scrape_CIK(CIK)
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



