# Stock Analyzer

A graphical Python tool for analyzing stock market data with technical indicators, strategy backtesting, and watchlist management.

## Features

- **Interactive GUI** - Modern Tkinter-based interface
- **Technical Indicators** - SMA (20, 50, 200), EMA (9, 26), RSI, MACD, Bollinger Bands, VWAP, ATR
- **Strategy Backtesting** - Test trading strategies with visual entry/exit signals
- **Watchlist Management** - Save and manage favorite stock tickers
- **Real-time Data** - Fetch live stock data via yfinance

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/purelmnz/StockAnalyzerFinal.git
   cd StockAnalyzerFinal
   ```

2. Install dependencies:
   ```bash
   pip install pandas yfinance matplotlib numpy
   ```

## Usage

Run the GUI application:

```bash
python gui_stock_analyzer_pro.py
```

### Main Features

- **Search** - Enter any ticker symbol (e.g., AAPL, TSLA, QQQ) to analyze
- **Indicators** - Toggle technical indicators from the sidebar
- **Time Range** - Select from 1M, 3M, 6M, 1Y, 2Y, 5Y timeframes
- **Strategies** - Choose backtesting strategies:
  - SMA Cross - 50/200 SMA crossover
  - EMA Cross - 9/26 EMA crossover
  - RSI Oversold/Overbought - Buy when RSI < 30, sell when > 70
  - Bollinger Bounce - Buy at lower band, sell at upper band
- **Watchlist** - Save your favorite stocks for quick access

## Technologies

- Python 3.x
- pandas
- yfinance
- matplotlib
- numpy
- Tkinter

## License

MIT
