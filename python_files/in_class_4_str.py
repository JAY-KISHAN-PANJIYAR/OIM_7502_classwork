import datetime as dt
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick  # helpful for plotting percentage
import seaborn as sb  # optional to set plot theme

sb.set_theme(style="whitegrid")  # setting a nice plot theme

# Define default date range for the class constructor
DEFAULT_START = dt.date.isoformat(dt.date.today() - dt.timedelta(days=365))
DEFAULT_END = dt.date.isoformat(dt.date.today())


class Stock:
    """
    A class for downloading, analyzing, and plotting historical stock data.
    """

    def __init__(self, symbol, start=DEFAULT_START, end=DEFAULT_END):
        """
        Initializes the Stock object with a ticker symbol and date range.
        The data is downloaded immediately upon instantiation.

        :param symbol: The stock ticker symbol (e.g., 'AAPL').
        :param start: Starting date for historical data in ISO format (YYYY-MM-DD).
        :param end: Ending date for historical data in ISO format (YYYY-MM-DD).
        """
        self.symbol = symbol.upper()
        self.start = start
        self.end = end
        # get_data returns the DataFrame, which is stored in self.data
        self.data = self.get_data()

    def calc_returns(self, df):
        """
        Helper method that adds change and instantaneous return columns to the DataFrame.

        :param df: The pandas DataFrame containing stock price data.
        :return: The modified DataFrame.
        """
        if df.empty:
            print("Error: DataFrame is empty; cannot calculate returns.")
            return df

        # 1. Calculate 'change' (daily percentage return)
        # difference between the close to close price relative to the previous day’s close
        df['change'] = df['Close'].pct_change().round(4)

        # 2. Calculate 'instant_return' (daily instantaneous rate of return)
        # np.log([closing_price]).diff().round(4)
        df['instant_return'] = np.log(df['Close']).diff().round(4)

        return df

    def get_data(self):
        """
        Downloads historical stock price data using yfinance based on the
        symbol, start, and end dates defined in the constructor.
        It calls calc_returns before returning the data.

        :return: A pandas DataFrame with historical data and calculated returns,
                 or None if data download fails or is empty.
        """
        print(f"Downloading data for {self.symbol} from {self.start} to {self.end}...")

        try:
            # Download the data
            data = yf.download(self.symbol, start=self.start, end=self.end, progress=False)

            if data.empty:
                print(f"Warning: No data found for {self.symbol} in the specified range.")
                return None

            # Ensure the index is a pandas Datetime object (yfinance usually handles this)
            data.index = pd.to_datetime(data.index)

            # Enrich data with returns
            data = self.calc_returns(data)

            print(f"Data successfully downloaded and returns calculated for {self.symbol}.")
            return data

        except Exception as e:
            print(f"An error occurred while downloading data for {self.symbol}: {e}")
            return None

    def plot_return_dist(self):
        """
        Plots a well-formatted histogram of the daily instantaneous returns.
        """
        if self.data is None or 'instant_return' not in self.data.columns:
            print("Error: Data must be downloaded and returns calculated before plotting.")
            return

        # Drop the first NaN value from the return calculation
        returns = self.data['instant_return'].dropna()

        plt.figure(figsize=(10, 6))
        # Use a nice color and clear edge for visibility
        returns.hist(bins=50, edgecolor='white', alpha=0.9, color='#1f77b4')
        plt.title(f'Distribution of Instantaneous Daily Returns for {self.symbol}', fontsize=16)
        plt.xlabel('Instantaneous Return (Log Return)', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)

        # Add a line for the mean return
        plt.axvline(returns.mean(), color='red', linestyle='dashed', linewidth=2, label=f'Mean: {returns.mean():.4f}')
        plt.legend()
        plt.tight_layout()
        plt.show()

    def plot_performance(self):
        """
        Plots a well-formatted line graph of the stock’s performance over the
        collected data range, shown as a percent gain/loss.
        """
        if self.data is None or 'change' not in self.data.columns:
            print("Error: Data must be downloaded and returns calculated before plotting performance.")
            return

        # Calculate cumulative performance starting at 100 (for percentage visualization)
        performance = (1 + self.data['change'].fillna(0)).cumprod() * 100

        plt.figure(figsize=(12, 7))
        performance.plot(linewidth=3, color='#2ca02c')  # Use a distinct green color

        # Formatting the plot
        plt.title(f'{self.symbol} Cumulative Performance (Percent Gain/Loss)', fontsize=18, pad=20)
        plt.xlabel('Date', fontsize=14)
        plt.ylabel('Performance Index (Start = 100)', fontsize=14)

        # Define a function to format the y-axis labels as percentage change relative to 100
        def format_y_axis(y, pos):
            return f'{y - 100:+.0f}%'  # + sign for positive numbers

        # Apply the custom formatter
        plt.gca().yaxis.set_major_formatter(mtick.FuncFormatter(format_y_axis))

        # Draw a line at the starting point (100)
        plt.axhline(100, color='grey', linestyle='--', linewidth=1.5, label='Initial Value (0% Change)')

        # Add total performance annotation
        end_val = performance.iloc[-1]
        gain_loss = end_val - 100
        color = 'green' if gain_loss >= 0 else 'red'

        plt.text(performance.index[-1], performance.iloc[-1] * 0.98,
                 f'Total Change: {gain_loss:+.2f}%',
                 horizontalalignment='right', verticalalignment='top',
                 fontsize=12, color=color, fontweight='bold')

        plt.legend()
        plt.tight_layout()
        plt.show()


def main():
    # uncomment (remove pass) code below to test
    stock_symbol = 'MSFT'  # Test object: Microsoft
    # 1. Instantiate a test object (uses default one-year range)
    test = Stock(symbol=stock_symbol)

    if test.data is not None:
        # 2. Access the data attribute
        print("\n--- Downloaded Data and Returns (Last 5 days) ---")
        print(test.data[['Close', 'change', 'instant_return']].tail())

        print("\n--- Generating Plots ---")
        # 3. Generate the two plots
        test.plot_performance()
        test.plot_return_dist()
    else:
        print(f"Could not run analysis for {stock_symbol} due to data download failure.")


if __name__ == '__main__':
    main()
