# openinsiderscraper

This Python script is designed to scrape insider trading data from the openinsider website for a list of stock tickers. It handles scraping, data aggregation and saving the results to a CSV file.

# How does it work

The script scrapes data about the given tickers and appends any new rows (not yet scraped) to the CSV file.

# Const parameters

There are 3 const parameters that you should change freely.
- `link` this is the link to CSV file
- `default_ticker_link` this is the link to file with default tickers to scrape if no other arguments are present
- `num_processes` this is the default number of processes the scraper will run on

# Using tickers in a file

The file needs to be a `.txt` one with tickers placed line by line.

# How to run it

To run the script, run: `python <path_to_script>`
- If you don't specify any parameters, it will scrape tickers from the default file.
- You can also pass tickers as command-line arguments.
- Alternatively, use the `-f` option to specify a file of tickers to scrape: `python <path_to_script> -f <path_to_file>`


