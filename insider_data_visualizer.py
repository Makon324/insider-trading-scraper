import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.dates import DateFormatter
import sqlite3
from adjustText import adjust_text
from datetime import datetime, timedelta
import argparse
import seaborn as sns
import os
from dotenv import load_dotenv

## ENV VARIABLES ##

load_dotenv()

script_dir = Path(__file__).resolve().parent  # path to parent folder of the script

link = script_dir / os.getenv("LINK", "scrapes.csv")  # link to file with scraped data - can be any of the following types: '.csv', '.txt', '.xlsx', '.db'

csv_sep = os.getenv("CSV_SEP", ';')  # separator in case link is .csv or .txt file

default_ticker_link = script_dir / os.getenv("TICKER_LINK", "default_tickers.txt")  # link to txt with default ticker list

#######


def generate_labels(df):
    current_date = datetime.min
    labels = []
    labels_dates = []
    for index, row in df.iterrows():
        # Check if current row's Filing Date is different from the last processed date
        if row["Filing Date"].date() != current_date.date():
            current_date = row["Filing Date"]
            labels.append(f"Date: {current_date}")  # Start a new label with the date
            labels_dates.append(current_date)
        elif row["Filing Date"] != current_date:
            labels[-1] += "\n----------------------\n" + f"Date: {current_date}"

        # Append the details to the current label
        labels[-1] += (
            f"\n----------------------\n"
            f"TD: {row['Trade Date'].date()}\n"
            f"TT: {row['Trade Type']}\n"
            f"IN: {row['Insider Name']}\n"
            f"T: {row['Title']}\n"
            f"P: {row['Price']} Qty: {row['Qty']}"
        )

    return (labels, labels_dates)




if __name__ == "__main__":

    ticker = ""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    parser = argparse.ArgumentParser(description="")

    # Add argparse options for -a, -b, -c (and similar options)
    parser.add_argument('-sd', type=str, help="Provide start date (%y-%m-$d)")
    parser.add_argument('-ed', type=str, help="Provide end date (%y-%m-$d)")
    parser.add_argument('-s', type=str, help="Provide file with scrapes")

    # Use `parse_known_args()` to allow argparse to handle the first few arguments
    args, unknown = parser.parse_known_args()

    if args.sd is not None:
        start_date = datetime.strptime(args.sd, '%Y-%m-%d')
    if args.ed is not None:
        end_date = datetime.strptime(args.ed, '%Y-%m-%d')
    if args.s is not None:
        link = args.s

    if not unknown:
        print("No ticker")
        exit()

    ticker = unknown[0]

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

    # delete everything except ticker
    df = df[df["Ticker"] == ticker]

    # Parse dates
    df["Filing Date"] = pd.to_datetime(df["Filing Date"], format="%Y-%m-%d %H:%M:%S")
    df["Trade Date"] = pd.to_datetime(df["Trade Date"], format="%Y-%m-%d")

    # Filter the dataframe to include only rows within the date range
    df = df[(df["Filing Date"] >= pd.to_datetime(start_date, format="%Y-%m-%d")) & (df["Filing Date"] <= pd.to_datetime(end_date, format="%Y-%m-%d"))]

    # Other filters
    df = df[df["Trade Type"].isin(["P - Purchase", "S - Sale"])]

    # Order by Filing Date
    df = df.sort_values(by=["Filing Date", "Trade Date"], ascending=[True, False]).reset_index(drop=True)

    # Generate labels
    labels, labels_dates = generate_labels(df)

    # Sort labels
    labels, labels_dates = zip(*sorted(zip(labels, labels_dates), key=lambda x: x[1]))

    # Fetch stock data using yfinance
    stock_data = yf.download(ticker, start=start_date, end=end_date)
    min_stock_price = stock_data['Close'].min()
    max_stock_price = stock_data['Close'].max()
    spn_stock_price = max_stock_price - min_stock_price

    # Create the Seaborn line plot
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=stock_data, x=stock_data.index, y='Close', label=f'{ticker} Close Price', color='blue')

    # Enhance the plot
    plt.title(f"{ticker} Stock Prices with Insider Trades")
    plt.xlabel("Date")
    plt.ylabel("Close Price (USD)")
    plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.grid(alpha=0.3)

    # Add annotations
    texts = []
    for label, label_date in zip(labels, labels_dates):
        # Find the nearest stock price to the label_date
        nearest_idx = stock_data.index.get_indexer([label_date], method='nearest')[0]
        nearest_stock_price = stock_data.iloc[nearest_idx]['Close']

        # Set color based on the label type
        color = 'green' if 'P - Purchase' in label else 'red' if 'S - Sale' in label else 'black'

        # Annotate the point
        text = plt.annotate(
            label,
            xy=(label_date, nearest_stock_price),
            xytext=(label_date, nearest_stock_price * (0.7 + 0.5 * (len(texts) % 2))), # Alternate positions to avoid overlap
            arrowprops=dict(facecolor='black', arrowstyle='->'),
            fontsize=6,
            bbox=dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.7)
        )
        texts.append(text)

    # Adjust positions to avoid overlap
    adjust_text(texts)

    # Add legend and finalize the plot
    plt.legend()
    plt.tight_layout()
    plt.show()





