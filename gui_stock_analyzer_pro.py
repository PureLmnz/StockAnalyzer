import tkinter as tk
from tkinter import ttk, messagebox
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import json
import os
import threading
import time

WATCHLIST_FILE = "watchlist.json"

INDICATOR_PRESETS = {
    "SMA": {"func": "sma", "params": {"length": 20}, "color": "#FFD700"},
    "SMA-50": {"func": "sma", "params": {"length": 50}, "color": "#00BFFF"},
    "SMA-200": {"func": "sma", "params": {"length": 200}, "color": "#FF6B6B"},
    "EMA-9": {"func": "ema", "params": {"length": 12}, "color": "#00FF88"},
    "EMA-26": {"func": "ema", "params": {"length": 26}, "color": "#FF00FF"},
    "RSI": {"func": "rsi", "params": {"length": 14}, "color": "#FFA500", "panel": "separate"},
    "MACD": {"func": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "color": "#00BFFF", "panel": "separate"},
    "BBANDS": {"func": "bbands", "params": {"length": 20, "std": 2}, "color": "#9370DB"},
    "VWAP": {"func": "vwap", "params": {}, "color": "#FF8C00"},
    "ATR": {"func": "atr", "params": {"length": 14}, "color": "#8B4513", "panel": "separate"},
}

class StockAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Analyzer Pro - with Strategy Backtesting")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")

        self.watchlist = []
        self.current_data = None
        self.current_ticker = None
        self.live_refresh = False
        self.refresh_thread = None
        self.stop_refresh = threading.Event()
        self.indicator_data = {}
        self.active_indicators = set()

        self.timeframe_options = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo"]
        self.period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

        self.load_watchlist()
        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=("Arial", 10))
        style.configure("TButton", background="#2d2d2d", foreground="#ffffff", font=("Arial", 10), borderwidth=1)
        style.map("TButton", background=[("active", "#3d3d3d")])
        style.configure("Treeview", background="#2d2d2d", foreground="#ffffff", fieldbackground="#2d2d2d")
        style.configure("Treeview.Heading", background="#3d3d3d", foreground="#ffffff")
        style.map("Treeview", background=[("selected", "#007acc")])

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.analyze_tab = ttk.Frame(self.notebook)
        self.strategy_tab = ttk.Frame(self.notebook)
        self.backtest_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.analyze_tab, text="  Analyze  ")
        self.notebook.add(self.strategy_tab, text="  Strategy Builder  ")
        self.notebook.add(self.backtest_tab, text="  Backtest Results  ")

        self.create_analyze_tab()
        self.create_strategy_tab()
        self.create_backtest_tab()

        status_bar = ttk.Label(self.root, text="Ready", relief="sunken", anchor="w")
        status_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.status_var = status_bar

    def create_analyze_tab(self):
        top_frame = ttk.Frame(self.analyze_tab)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(top_frame, text="Ticker:").pack(side="left", padx=5)
        self.ticker_entry = ttk.Entry(top_frame, width=10, font=("Arial", 12))
        self.ticker_entry.pack(side="left", padx=5)
        self.ticker_entry.bind("<Return>", lambda e: self.analyze_stock())

        ttk.Label(top_frame, text="Period:").pack(side="left", padx=5)
        self.period_combo = ttk.Combobox(top_frame, values=self.period_options, width=8, state="readonly")
        self.period_combo.set("60d")
        self.period_combo.pack(side="left", padx=5)

        ttk.Label(top_frame, text="Interval:").pack(side="left", padx=5)
        self.interval_combo = ttk.Combobox(top_frame, values=self.timeframe_options, width=8, state="readonly")
        self.interval_combo.set("15m")
        self.interval_combo.pack(side="left", padx=5)

        ttk.Button(top_frame, text="Analyze", command=self.analyze_stock).pack(side="left", padx=10)

        self.live_btn = tk.Button(top_frame, text="Live: OFF", command=self.toggle_live, bg="#2d2d2d", fg="#ffffff", relief="raised")
        self.live_btn.pack(side="left", padx=5)

        self.chart_type_var = tk.StringVar(value="line")
        ttk.Radiobutton(top_frame, text="Line", variable=self.chart_type_var, value="line").pack(side="left", padx=5)
        ttk.Radiobutton(top_frame, text="Candle", variable=self.chart_type_var, value="candle").pack(side="left", padx=5)

        main_frame = ttk.Frame(self.analyze_tab)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ttk.Label(left_frame, text="Stock Data", font=("Arial", 11, "bold")).pack(anchor="w")
        self.data_tree = ttk.Treeview(left_frame, show="headings", height=8)
        columns = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        self.data_tree["columns"] = columns
        for col in columns:
            self.data_tree.heading(col, text=col)
            self.data_tree.column(col, width=90, anchor="center")
        self.data_tree.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        right_frame = ttk.Frame(main_frame, width=200)
        right_frame.pack(side="right", fill="both", padx=(5, 0))
        right_frame.pack_propagate(False)

        ttk.Label(right_frame, text="Watchlist", font=("Arial", 11, "bold")).pack(anchor="w")
        self.watchlistbox = tk.Listbox(right_frame, bg="#2d2d2d", fg="#ffffff", selectbackground="#007acc")
        self.watchlistbox.pack(fill="both", expand=True, pady=5)
        self.watchlistbox.bind("<Double-Button-1>", self.load_from_watchlist)

        watchlist_btn_frame = ttk.Frame(right_frame)
        watchlist_btn_frame.pack(fill="x", pady=5)
        ttk.Button(watchlist_btn_frame, text="Add", command=self.add_to_watchlist).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(watchlist_btn_frame, text="Remove", command=self.remove_from_watchlist).pack(side="left", fill="x", expand=True, padx=2)

        self.update_watchlist_display()

        chart_frame = ttk.Frame(self.analyze_tab)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ttk.Label(chart_frame, text="Chart", font=("Arial", 11, "bold")).pack(anchor="w")
        self.fig = Figure(figsize=(10, 4), facecolor="#1e1e1e")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#1e1e1e")
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def create_strategy_tab(self):
        top_frame = ttk.Frame(self.strategy_tab)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(top_frame, text="Ticker:").pack(side="left", padx=5)
        self.strat_ticker_entry = ttk.Entry(top_frame, width=10, font=("Arial", 12))
        self.strat_ticker_entry.pack(side="left", padx=5)

        ttk.Label(top_frame, text="Period:").pack(side="left", padx=5)
        self.strat_period_combo = ttk.Combobox(top_frame, values=self.period_options, width=8, state="readonly")
        self.strat_period_combo.set("1y")
        self.strat_period_combo.pack(side="left", padx=5)

        ttk.Label(top_frame, text="Interval:").pack(side="left", padx=5)
        self.strat_interval_combo = ttk.Combobox(top_frame, values=self.timeframe_options, width=8, state="readonly")
        self.strat_interval_combo.set("1d")
        self.strat_interval_combo.pack(side="left", padx=5)

        ttk.Button(top_frame, text="Load Data", command=self.load_strategy_data).pack(side="left", padx=10)

        strategy_frame = ttk.LabelFrame(self.strategy_tab, text="Strategy Builder", padding=10)
        strategy_frame.pack(fill="both", expand=True, padx=10, pady=5)

        left_col = ttk.Frame(strategy_frame)
        left_col.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(left_col, text="Entry Conditions", font=("Arial", 10, "bold")).pack(anchor="w")
        
        ttk.Label(left_col, text="Strategy Type:").pack(anchor="w", pady=(5,0))
        self.entry_strategy_var = tk.StringVar(value="SMA_CROSS_VOLUME")
        strategy_types = [
            "SMA_CROSS_VOLUME - SMA cross with volume filter (0-1 DTE)",
            "SMA_CROSS - Fast SMA crosses above/below Slow SMA",
            "EMA_CROSS - Fast EMA crosses above Slow EMA",
            "RSI_OVERSOLD - RSI crosses above threshold",
            "RSI_OVERBOUGHT - RSI crosses below threshold",
            "PRICE_VS_SMA - Price crosses above/below SMA",
        ]
        strat_combo = ttk.Combobox(left_col, values=strategy_types, textvariable=self.entry_strategy_var, state="readonly", width=45)
        strat_combo.pack(fill="x", pady=5)
        strat_combo.bind("<<ComboboxSelected>>", self.update_strategy_params)

        self.entry_params_frame = ttk.Frame(left_col)
        self.entry_params_frame.pack(fill="x", pady=5)

        ttk.Label(left_col, text="Strategy Parameters:", font=("Arial", 9, "bold")).pack(anchor="w", pady=(10,5))
        
        ttk.Label(left_col, text="SMA Period (e.g., 200):").pack(anchor="w")
        self.sma_period_entry = ttk.Entry(left_col, width=10)
        self.sma_period_entry.insert(0, "200")
        self.sma_period_entry.pack(anchor="w", pady=2)

        ttk.Label(left_col, text="Volume Multiplier (e.g., 1.5 = 1.5x avg):").pack(anchor="w")
        self.volume_mult_entry = ttk.Entry(left_col, width=10)
        self.volume_mult_entry.insert(0, "0")
        self.volume_mult_entry.pack(anchor="w", pady=2)

        ttk.Label(left_col, text="Volume Avg Period (bars):").pack(anchor="w")
        self.volume_period_entry = ttk.Entry(left_col, width=10)
        self.volume_period_entry.insert(0, "20")
        self.volume_period_entry.pack(anchor="w", pady=2)

        ttk.Label(left_col, text="Exit After X Bars (0=hold to end):").pack(anchor="w")
        self.exit_bars_entry = ttk.Entry(left_col, width=10)
        self.exit_bars_entry.insert(0, "0")
        self.exit_bars_entry.pack(anchor="w", pady=2)

        ttk.Label(left_col, text="Entry Direction:").pack(anchor="w")
        self.direction_var = tk.StringVar(value="BOTH")
        tk.Radiobutton(left_col, text="Long Only (Calls)", variable=self.direction_var, value="LONG", bg="#1e1e1e", fg="#ffffff", selectcolor="#2d2d2d").pack(anchor="w")
        tk.Radiobutton(left_col, text="Short Only (Puts)", variable=self.direction_var, value="SHORT", bg="#1e1e1e", fg="#ffffff", selectcolor="#2d2d2d").pack(anchor="w")
        tk.Radiobutton(left_col, text="Both Directions", variable=self.direction_var, value="BOTH", bg="#1e1e1e", fg="#ffffff", selectcolor="#2d2d2d").pack(anchor="w")

        right_col = ttk.Frame(strategy_frame)
        right_col.pack(side="right", fill="both", expand=True, padx=5)

        ttk.Label(right_col, text="Indicators to Display on Chart", font=("Arial", 10, "bold")).pack(anchor="w")

        self.indicator_vars = {}
        indicator_frame = ttk.Frame(right_col)
        indicator_frame.pack(fill="both", expand=True, pady=5)

        row, col = 0, 0
        for name in ["SMA-50", "SMA-200", "EMA-9", "EMA-26", "RSI", "MACD", "BBANDS", "VWAP", "ATR"]:
            var = tk.BooleanVar(value=name in ["SMA-50", "SMA-200"])
            self.indicator_vars[name] = var
            cb = tk.Checkbutton(indicator_frame, text=name, variable=var, bg="#1e1e1e", fg="#ffffff", selectcolor="#2d2d2d")
            cb.grid(row=row, column=col, sticky="w", padx=10, pady=2)
            col += 1
            if col > 2:
                col = 0
                row += 1

        ttk.Label(right_col, text="Chart Settings:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10,5))
        
        self.show_signals_var = tk.BooleanVar(value=True)
        tk.Checkbutton(right_col, text="Show Buy/Sell Signals on Chart", variable=self.show_signals_var, bg="#1e1e1e", fg="#ffffff", selectcolor="#2d2d2d").pack(anchor="w")

        ttk.Button(right_col, text="Run Backtest", command=self.run_backtest).pack(fill="x", pady=15)

        chart_frame = ttk.Frame(self.strategy_tab)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ttk.Label(chart_frame, text="Strategy Chart", font=("Arial", 11, "bold")).pack(anchor="w")
        self.strat_fig = Figure(figsize=(12, 5), facecolor="#1e1e1e")
        self.strat_ax = self.strat_fig.add_subplot(111)
        self.strat_ax.set_facecolor("#1e1e1e")
        self.strat_canvas = FigureCanvasTkAgg(self.strat_fig, chart_frame)
        self.strat_canvas.get_tk_widget().pack(fill="both", expand=True)

    def create_backtest_tab(self):
        control_frame = ttk.Frame(self.backtest_tab)
        control_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(control_frame, text="Backtest Settings:", font=("Arial", 11, "bold")).pack(side="left", padx=10)

        ttk.Label(control_frame, text="Initial Capital:").pack(side="left", padx=5)
        self.initial_capital_entry = ttk.Entry(control_frame, width=12)
        self.initial_capital_entry.insert(0, "100000")
        self.initial_capital_entry.pack(side="left", padx=5)

        ttk.Label(control_frame, text="Commission %:").pack(side="left", padx=5)
        self.commission_entry = ttk.Entry(control_frame, width=8)
        self.commission_entry.insert(0, "0.1")
        self.commission_entry.pack(side="left", padx=5)

        results_frame = ttk.LabelFrame(self.backtest_tab, text="Performance Metrics", padding=15)
        results_frame.pack(fill="x", padx=10, pady=5)

        self.metrics_labels = {}
        metrics = [
            ("Total Return:", "total_return", "+0.00%"),
            ("Win Rate:", "win_rate", "0.00%"),
            ("Sharpe Ratio:", "sharpe_ratio", "0.00"),
            ("Total Trades:", "total_trades", "0"),
            ("Profitable Trades:", "profitable_trades", "0"),
            ("Losing Trades:", "losing_trades", "0"),
            ("Best Trade:", "best_trade", "+0.00%"),
            ("Worst Trade:", "worst_trade", "-0.00%"),
            ("Avg Profit:", "avg_profit", "+0.00%"),
            ("Avg Loss:", "avg_loss", "-0.00%"),
        ]

        for i, (label, key, default) in enumerate(metrics):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(results_frame, text=label, font=("Arial", 10, "bold")).grid(row=row, column=col, sticky="w", padx=10, pady=5)
            value_label = ttk.Label(results_frame, text=default, foreground="#00ff88" if "Return" in label else "#ffffff")
            value_label.grid(row=row, column=col+1, sticky="w", padx=10, pady=5)
            self.metrics_labels[key] = value_label

        trades_frame = ttk.LabelFrame(self.backtest_tab, text="Trade History", padding=10)
        trades_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.trades_tree = ttk.Treeview(trades_frame, show="headings", height=12)
        trade_columns = ["#", "Entry Date", "Entry Price", "Exit Date", "Exit Price", "P&L %", "P&L $", "Type"]
        self.trades_tree["columns"] = trade_columns
        for col in trade_columns:
            self.trades_tree.heading(col, text=col)
            self.trades_tree.column(col, width=100, anchor="center")
        self.trades_tree.pack(fill="both", expand=True)

        trades_scroll = ttk.Scrollbar(trades_frame, orient="vertical", command=self.trades_tree.yview)
        self.trades_tree.configure(yscrollcommand=trades_scroll.set)
        trades_scroll.pack(side="right", fill="y")

    def update_strategy_params(self, event=None):
        pass

    def load_strategy_data(self):
        ticker = self.strat_ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Input Error", "Please enter a ticker symbol")
            return

        period = self.strat_period_combo.get()
        interval = self.strat_interval_combo.get()

        self.status_var.config(text=f"Loading {ticker} data for backtesting...")
        
        try:
            data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
            
            if data.empty:
                messagebox.showerror("Error", f"No data found for ticker '{ticker}'")
                self.status_var.config(text="Ready")
                return

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            self.strategy_data = data
            self.strategy_ticker = ticker
            self.calculate_indicators(data)
            self.plot_strategy_chart(data, ticker)
            self.status_var.config(text=f"Loaded {ticker} - {len(data)} bars")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")
            self.status_var.config(text="Error")

    def calculate_indicators(self, data):
        close = data["Close"]
        high = data["High"]
        low = data["Low"]
        volume = data["Volume"]

        data["SMA_50"] = close.rolling(window=50).mean()
        data["SMA_200"] = close.rolling(window=200).mean()
        data["EMA_9"] = close.ewm(span=9, adjust=False).mean()
        data["EMA_26"] = close.ewm(span=26, adjust=False).mean()

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data["RSI"] = 100 - (100 / (1 + rs))

        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        data["MACD"] = exp1 - exp2
        data["MACD_SIGNAL"] = data["MACD"].ewm(span=9, adjust=False).mean()
        data["MACD_HIST"] = data["MACD"] - data["MACD_SIGNAL"]

        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        data["BB_UPPER"] = sma20 + (std20 * 2)
        data["BB_MID"] = sma20
        data["BB_LOWER"] = sma20 - (std20 * 2)

        data["VWAP"] = (high + low + close) / 3
        data["VWAP"] = (data["VWAP"] * volume).cumsum() / volume.cumsum()

        high_low = high - low
        high_close = abs(high - close.shift())
        low_close = abs(low - close.shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data["ATR"] = true_range.rolling(window=14).mean()

        self.strategy_data = data

    def plot_strategy_chart(self, data, ticker):
        self.strat_ax.clear()
        self.strat_ax.set_facecolor("#1e1e1e")

        close = data["Close"].values
        dates = range(len(close))

        close_vals = []
        for c in close:
            if hasattr(c, 'item'):
                close_vals.append(c.item())
            else:
                close_vals.append(c)

        self.strat_ax.plot(dates, close_vals, color="#ffffff", linewidth=1.5, label="Close")

        sma_period = int(self.sma_period_entry.get())
        sma = data["Close"].rolling(window=sma_period).mean()
        sma_vals = [s.item() if hasattr(s, 'item') else s for s in sma.values]
        self.strat_ax.plot(dates, sma_vals, color="#FF6B6B", linewidth=1.5, label=f"SMA-{sma_period}")

        active_indicators = [name for name, var in self.indicator_vars.items() if var.get()]

        colors = {"SMA-50": "#FFD700", "SMA-200": "#FF6B6B", "EMA-9": "#00FF88", "EMA-26": "#FF00FF", 
                  "BBANDS": "#9370DB", "VWAP": "#FF8C00", "ATR": "#8B4513", "RSI": "#FFA500", "MACD": "#00BFFF"}

        for ind_name in active_indicators:
            if ind_name == "SMA-50":
                col = "SMA_50"
            elif ind_name == "SMA-200":
                col = "SMA_200"
            elif ind_name == "EMA-9":
                col = "EMA_9"
            elif ind_name == "EMA-26":
                col = "EMA_26"
            elif ind_name == "RSI":
                continue
            elif ind_name == "MACD":
                continue
            elif ind_name == "BBANDS":
                for bb_col in ["BB_UPPER", "BB_MID", "BB_LOWER"]:
                    if bb_col in data.columns:
                        vals = data[bb_col].values
                        clean_vals = [v.item() if hasattr(v, 'item') else v for v in vals]
                        self.strat_ax.plot(dates, clean_vals, color=colors.get(ind_name, "#fff"), linewidth=0.8, alpha=0.7, label=bb_col)
                continue
            elif ind_name == "VWAP":
                col = "VWAP"
            elif ind_name == "ATR":
                continue
            else:
                continue

            if col in data.columns:
                vals = data[col].values
                clean_vals = [v.item() if hasattr(v, 'item') else v for v in vals]
                self.strat_ax.plot(dates, clean_vals, color=colors.get(ind_name, "#fff"), linewidth=1.2, label=col)

        self.strat_ax.set_title(f"{ticker} - Strategy Chart", color="#ffffff", fontsize=12)
        self.strat_ax.set_xlabel("Time", color="#888888")
        self.strat_ax.set_ylabel("Price", color="#888888")
        self.strat_ax.tick_params(colors="#888888")
        for spine in self.strat_ax.spines.values():
            spine.set_color("#444444")
        self.strat_ax.grid(True, alpha=0.2, color="#444444")
        self.strat_ax.legend(loc="upper left", fontsize=8, facecolor="#1e1e1e", labelcolor="#888888")

        self.strat_fig.tight_layout()
        self.strat_canvas.draw()

    def run_backtest(self):
        if not hasattr(self, 'strategy_data') or self.strategy_data is None:
            messagebox.showwarning("No Data", "Please load data first")
            return

        strategy = self.entry_strategy_var.get()
        sma_period = int(self.sma_period_entry.get())
        volume_mult = float(self.volume_mult_entry.get())
        volume_period = int(self.volume_period_entry.get())
        exit_bars = int(self.exit_bars_entry.get())
        direction = self.direction_var.get()
        initial_capital = float(self.initial_capital_entry.get())
        commission = float(self.commission_entry.get()) / 100

        data = self.strategy_data.copy()

        data["SMA"] = data["Close"].rolling(window=sma_period).mean()
        data["AVG_VOLUME"] = data["Volume"].rolling(window=volume_period).mean()
        
        if volume_mult > 0:
            data["VOLUME_OK"] = data["Volume"] > (data["AVG_VOLUME"] * volume_mult)
        else:
            data["VOLUME_OK"] = True

        close_vals = data["Close"].values
        sma_vals = data["SMA"].values
        
        close_clean = [c.item() if hasattr(c, 'item') else c for c in close_vals]
        sma_clean = [s.item() if hasattr(s, 'item') else s for s in sma_vals]
        
        if "SMA_CROSS_VOLUME" in strategy or "PRICE_VS_SMA" in strategy:
            long_entry = [False] * len(data)
            short_entry = [False] * len(data)
            long_exit = [False] * len(data)
            short_exit = [False] * len(data)
            
            position_type = [None] * len(data)
            entry_bar = [0] * len(data)
            
            in_long = False
            in_short = False
            entry_idx = 0
            
            for i in range(1, len(data)):
                price = close_clean[i]
                prev_price = close_clean[i-1]
                sma_val = sma_clean[i]
                prev_sma = sma_clean[i-1]
                vol_ok = data["VOLUME_OK"].iloc[i] if pd.notna(data["VOLUME_OK"].iloc[i]) else False
                
                if not in_long and not in_short:
                    if prev_price <= prev_sma and price > sma_val and vol_ok and direction in ["LONG", "BOTH"]:
                        long_entry[i] = True
                        in_long = True
                        entry_idx = i
                        position_type[i] = "LONG"
                    elif prev_price >= prev_sma and price < sma_val and vol_ok and direction in ["SHORT", "BOTH"]:
                        short_entry[i] = True
                        in_short = True
                        entry_idx = i
                        position_type[i] = "SHORT"
                else:
                    if in_long:
                        should_exit = False
                        if exit_bars > 0 and (i - entry_idx) >= exit_bars:
                            should_exit = True
                        elif prev_price >= prev_sma and price < sma_val:
                            should_exit = True
                        
                        if should_exit:
                            long_exit[i] = True
                            in_long = False
                    
                    elif in_short:
                        should_exit = False
                        if exit_bars > 0 and (i - entry_idx) >= exit_bars:
                            should_exit = True
                        elif prev_price <= prev_sma and price > sma_val:
                            should_exit = True
                        
                        if should_exit:
                            short_exit[i] = True
                            in_short = False
            
            data["LONG_ENTRY"] = long_entry
            data["SHORT_ENTRY"] = short_entry
            data["LONG_EXIT"] = long_exit
            data["SHORT_EXIT"] = short_exit

        elif "SMA_CROSS" in strategy:
            fast_period = sma_period if sma_period < 100 else 50
            slow_period = 200
            
            fast_ma = data["Close"].rolling(window=fast_period).mean()
            slow_ma = data["Close"].rolling(window=slow_period).mean()
            
            data["LONG_ENTRY"] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            data["SHORT_ENTRY"] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            data["LONG_EXIT"] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            data["SHORT_EXIT"] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))

        elif "EMA_CROSS" in strategy:
            fast_ma = data["Close"].ewm(span=12, adjust=False).mean()
            slow_ma = data["Close"].ewm(span=26, adjust=False).mean()
            
            data["LONG_ENTRY"] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            data["SHORT_ENTRY"] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            data["LONG_EXIT"] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            data["SHORT_EXIT"] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))

        elif "RSI_OVERSOLD" in strategy:
            rsi_threshold = 30
            data["LONG_ENTRY"] = (data["RSI"] < rsi_threshold) & (data["RSI"].shift(1) >= rsi_threshold)
            data["SHORT_ENTRY"] = False
            data["LONG_EXIT"] = data["RSI"] > (100 - rsi_threshold)
            data["SHORT_EXIT"] = False

        elif "RSI_OVERBOUGHT" in strategy:
            rsi_threshold = 70
            data["LONG_ENTRY"] = False
            data["SHORT_ENTRY"] = (data["RSI"] > rsi_threshold) & (data["RSI"].shift(1) <= rsi_threshold)
            data["LONG_EXIT"] = False
            data["SHORT_EXIT"] = data["RSI"] < (100 - rsi_threshold)

        else:
            data["LONG_ENTRY"] = (data["SMA_50"] > data["SMA_200"]) & (data["SMA_50"].shift(1) <= data["SMA_200"].shift(1))
            data["SHORT_ENTRY"] = (data["SMA_50"] < data["SMA_200"]) & (data["SMA_50"].shift(1) >= data["SMA_200"].shift(1))
            data["LONG_EXIT"] = (data["SMA_50"] < data["SMA_200"]) & (data["SMA_50"].shift(1) >= data["SMA_200"].shift(1))
            data["SHORT_EXIT"] = (data["SMA_50"] > data["SMA_200"]) & (data["SMA_50"].shift(1) <= data["SMA_200"].shift(1))

        trades = self.execute_backtest_v2(data, initial_capital, commission, direction)
        self.display_backtest_results(trades, initial_capital)

        if self.show_signals_var.get():
            self.plot_strategy_with_signals(data, self.strategy_ticker, trades)

    def execute_backtest(self, data, initial_capital, commission):
        close = data["Close"].values
        entries = data["ENTRY_SIGNAL"].values
        exits = data["EXIT_SIGNAL"].values
        
        close_clean = [c.item() if hasattr(c, 'item') else c for c in close]

        capital = initial_capital
        position = 0
        entry_price = 0
        trades = []
        in_position = False

        for i in range(1, len(data)):
            price = close_clean[i]
            
            if entries[i] and not in_position:
                shares = int(capital / price)
                if shares > 0:
                    cost = shares * price * (1 + commission)
                    if cost <= capital:
                        capital -= cost
                        position = shares
                        entry_price = price
                        entry_date = data.index[i]
                        in_position = True
                        trade_type = "LONG"

            elif exits[i] and in_position:
                proceeds = position * price * (1 - commission)
                pnl = proceeds - (position * entry_price)
                pnl_pct = (pnl / (position * entry_price)) * 100
                exit_date = data.index[i]
                
                trades.append({
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "exit_date": exit_date,
                    "exit_price": price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "type": trade_type
                })
                
                capital += proceeds
                position = 0
                in_position = False

        if in_position:
            final_price = close_clean[-1]
            pnl = position * (final_price - entry_price)
            pnl_pct = (pnl / (position * entry_price)) * 100
            trades.append({
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": data.index[-1],
                "exit_price": final_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "type": "LONG (Open)"
            })

        self.backtest_trades = trades
        return trades

    def execute_backtest_v2(self, data, initial_capital, commission, direction):
        close = data["Close"].values
        close_clean = [c.item() if hasattr(c, 'item') else c for c in close]
        
        def to_bool_list(arr):
            result = []
            for v in arr:
                if hasattr(v, 'item'):
                    result.append(bool(v.item()))
                else:
                    result.append(bool(v))
            return result
        
        long_entries = to_bool_list(data["LONG_ENTRY"].values) if "LONG_ENTRY" in data.columns else [False] * len(data)
        short_entries = to_bool_list(data["SHORT_ENTRY"].values) if "SHORT_ENTRY" in data.columns else [False] * len(data)
        long_exits = to_bool_list(data["LONG_EXIT"].values) if "LONG_EXIT" in data.columns else [False] * len(data)
        short_exits = to_bool_list(data["SHORT_EXIT"].values) if "SHORT_EXIT" in data.columns else [False] * len(data)
        
        capital = initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        trade_type = "LONG"
        bars_held = 0
        trades = []
        in_position = False

        for i in range(1, len(data)):
            price = close_clean[i]
            bars_held += 1
            
            can_go_long = direction in ["LONG", "BOTH"]
            can_go_short = direction in ["SHORT", "BOTH"]
            
            if long_entries[i] and not in_position and can_go_long:
                shares = int(capital / price)
                if shares > 0:
                    cost = shares * price * (1 + commission)
                    if cost <= capital:
                        capital -= cost
                        position = shares
                        entry_price = price
                        entry_date = data.index[i]
                        in_position = True
                        trade_type = "LONG"
                        bars_held = 0

            elif short_entries[i] and not in_position and can_go_short:
                shares = int(capital / price)
                if shares > 0:
                    proceeds = shares * price * (1 - commission)
                    if proceeds <= capital:
                        capital += proceeds
                        position = shares
                        entry_price = price
                        entry_date = data.index[i]
                        in_position = True
                        trade_type = "SHORT"
                        bars_held = 0

            should_exit = False
            if in_position:
                if trade_type == "LONG" and (long_exits[i] or (bars_held > 1 and long_exits[i-1])):
                    should_exit = True
                elif trade_type == "SHORT" and (short_exits[i] or (bars_held > 1 and short_exits[i-1])):
                    should_exit = True
                
                exit_bars = int(self.exit_bars_entry.get()) if hasattr(self, 'exit_bars_entry') else 0
                if exit_bars > 0 and bars_held >= exit_bars:
                    should_exit = True
            
            if should_exit and in_position:
                if trade_type == "LONG":
                    proceeds = position * price * (1 - commission)
                    pnl = proceeds - (position * entry_price)
                    pnl_pct = (pnl / (position * entry_price)) * 100
                else:
                    cost = position * entry_price * (1 + commission)
                    proceeds = position * price * (1 - commission)
                    pnl = proceeds - cost
                    pnl_pct = (pnl / cost) * 100
                
                exit_date = data.index[i]
                
                trades.append({
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "exit_date": exit_date,
                    "exit_price": price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "type": trade_type
                })
                
                if trade_type == "LONG":
                    capital += proceeds
                else:
                    capital = capital - proceeds + (position * entry_price)
                
                position = 0
                in_position = False

        if in_position:
            final_price = close_clean[-1]
            if trade_type == "LONG":
                pnl = position * (final_price - entry_price)
                pnl_pct = (pnl / (position * entry_price)) * 100
            else:
                pnl = position * (entry_price - final_price)
                pnl_pct = (pnl / (position * entry_price)) * 100
            
            trades.append({
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": data.index[-1],
                "exit_price": final_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "type": f"{trade_type} (Open)"
            })

        self.backtest_trades = trades
        return trades

    def display_backtest_results(self, trades, initial_capital):
        if not trades:
            messagebox.showinfo("No Trades", "No trades were executed with this strategy")
            return

        total_return = sum(t["pnl"] for t in trades)
        total_return_pct = (total_return / initial_capital) * 100

        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]

        win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0

        if winning_trades:
            best_trade = max(t["pnl_pct"] for t in winning_trades)
            avg_profit = np.mean([t["pnl_pct"] for t in winning_trades])
        else:
            best_trade = 0
            avg_profit = 0

        if losing_trades:
            worst_trade = min(t["pnl_pct"] for t in losing_trades)
            avg_loss = np.mean([t["pnl_pct"] for t in losing_trades])
        else:
            worst_trade = 0
            avg_loss = 0

        returns = [t["pnl_pct"] / 100 for t in trades if t["pnl_pct"] != 0]
        if returns and len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        self.metrics_labels["total_return"].config(text=f"{total_return_pct:+.2f}%", foreground="#00ff88" if total_return_pct >= 0 else "#ff4444")
        self.metrics_labels["win_rate"].config(text=f"{win_rate:.2f}%")
        self.metrics_labels["sharpe_ratio"].config(text=f"{sharpe:.2f}")
        self.metrics_labels["total_trades"].config(text=str(len(trades)))
        self.metrics_labels["profitable_trades"].config(text=str(len(winning_trades)), foreground="#00ff88")
        self.metrics_labels["losing_trades"].config(text=str(len(losing_trades)), foreground="#ff4444")
        self.metrics_labels["best_trade"].config(text=f"{best_trade:+.2f}%", foreground="#00ff88")
        self.metrics_labels["worst_trade"].config(text=f"{worst_trade:+.2f}%", foreground="#ff4444")
        self.metrics_labels["avg_profit"].config(text=f"{avg_profit:+.2f}%", foreground="#00ff88")
        self.metrics_labels["avg_loss"].config(text=f"{avg_loss:+.2f}%", foreground="#ff4444")

        for item in self.trades_tree.get_children():
            self.trades_tree.delete(item)

        for i, trade in enumerate(trades, 1):
            entry_dt = str(trade["entry_date"])[:10] if hasattr(trade["entry_date"], "strftime") else str(trade["entry_date"])[:10]
            exit_dt = str(trade["exit_date"])[:10] if hasattr(trade["exit_date"], "strftime") else str(trade["exit_date"])[:10]
            
            values = [
                str(i),
                entry_dt,
                f"${trade['entry_price']:.2f}",
                exit_dt,
                f"${trade['exit_price']:.2f}",
                f"{trade['pnl_pct']:+.2f}%",
                f"${trade['pnl']:+.2f}",
                trade["type"]
            ]
            self.trades_tree.insert("", "end", values=values)

    def plot_strategy_with_signals(self, data, ticker, trades):
        self.strat_ax.clear()
        self.strat_ax.set_facecolor("#1e1e1e")

        close = data["Close"].values
        dates = range(len(close))
        close_vals = [c.item() if hasattr(c, 'item') else c for c in close]

        self.strat_ax.plot(dates, close_vals, color="#ffffff", linewidth=1.5, label="Close")

        if "SMA" in data.columns:
            sma_vals = [s.item() if hasattr(s, 'item') else s for s in data["SMA"].values]
            self.strat_ax.plot(dates, sma_vals, color="#FF6B6B", linewidth=1.5, label=f"SMA-{int(self.sma_period_entry.get())}")

        active_indicators = [name for name, var in self.indicator_vars.items() if var.get()]
        colors = {"SMA-50": "#FFD700", "SMA-200": "#FF6B6B", "EMA-9": "#00FF88", "EMA-26": "#FF00FF", 
                  "BBANDS": "#9370DB", "VWAP": "#FF8C00"}

        for ind_name in active_indicators:
            col_map = {"SMA-50": "SMA_50", "SMA-200": "SMA_200", "EMA-9": "EMA_9", "EMA-26": "EMA_26", "VWAP": "VWAP"}
            col = col_map.get(ind_name)
            if col and col in data.columns:
                vals = [v.item() if hasattr(v, 'item') else v for v in data[col].values]
                self.strat_ax.plot(dates, vals, color=colors.get(ind_name, "#fff"), linewidth=1.2, label=col)

        long_entry_x, long_entry_y = [], []
        short_entry_x, short_entry_y = [], []
        long_exit_x, long_exit_y = [], []
        short_exit_x, short_exit_y = [], []

        for trade in trades:
            entry_idx = data.index.get_loc(trade["entry_date"]) if trade["entry_date"] in data.index else None
            if entry_idx is not None:
                if "LONG" in trade["type"] and "SHORT" not in trade["type"]:
                    long_entry_x.append(entry_idx)
                    long_entry_y.append(trade["entry_price"])
                elif "SHORT" in trade["type"]:
                    short_entry_x.append(entry_idx)
                    short_entry_y.append(trade["entry_price"])

            if "Open" not in trade["type"]:
                exit_idx = data.index.get_loc(trade["exit_date"]) if trade["exit_date"] in data.index else None
                if exit_idx is not None:
                    if "LONG" in trade["type"] and "SHORT" not in trade["type"]:
                        long_exit_x.append(exit_idx)
                        long_exit_y.append(trade["exit_price"])
                    elif "SHORT" in trade["type"]:
                        short_exit_x.append(exit_idx)
                        short_exit_y.append(trade["exit_price"])

        if long_entry_x:
            self.strat_ax.scatter(long_entry_x, long_entry_y, color="#00ff88", marker="^", s=120, label="Long Entry", zorder=5)
        if long_exit_x:
            self.strat_ax.scatter(long_exit_x, long_exit_y, color="#00ff88", marker="v", s=120, label="Long Exit", zorder=5)
        if short_entry_x:
            self.strat_ax.scatter(short_entry_x, short_entry_y, color="#ff4444", marker="v", s=120, label="Short Entry", zorder=5)
        if short_exit_x:
            self.strat_ax.scatter(short_exit_x, short_exit_y, color="#ff4444", marker="^", s=120, label="Short Exit", zorder=5)

        self.strat_ax.set_title(f"{ticker} - Backtest Results", color="#ffffff", fontsize=12)
        self.strat_ax.set_xlabel("Time", color="#888888")
        self.strat_ax.set_ylabel("Price", color="#888888")
        self.strat_ax.tick_params(colors="#888888")
        for spine in self.strat_ax.spines.values():
            spine.set_color("#444444")
        self.strat_ax.grid(True, alpha=0.2, color="#444444")
        self.strat_ax.legend(loc="upper left", fontsize=8, facecolor="#1e1e1e", labelcolor="#888888")

        self.strat_fig.tight_layout()
        self.strat_canvas.draw()

    def analyze_stock(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Input Error", "Please enter a ticker symbol")
            return

        period = self.period_combo.get()
        interval = self.interval_combo.get()

        self.status_var.config(text=f"Downloading {ticker} data...")
        
        try:
            data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)

            if data.empty:
                messagebox.showerror("Error", f"No data found for ticker '{ticker}'")
                self.status_var.config(text="Ready")
                return

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            self.current_data = data
            self.current_ticker = ticker

            self.update_data_table(data)
            self.plot_chart(data, ticker)
            self.status_var.config(text=f"Loaded {ticker} - {len(data)} data points")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch data: {str(e)}")
            self.status_var.config(text="Error")

    def update_data_table(self, data):
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)

        display_data = data.tail(50).reset_index(drop=True)
        
        def get_val(series, key):
            val = series[key]
            if hasattr(val, 'item'):
                return val.item()
            return val
        
        for i in range(len(display_data)):
            row = display_data.iloc[i]
            dt_col = display_data.index[i]
            dt = dt_col.strftime("%Y-%m-%d %H:%M") if hasattr(dt_col, 'strftime') else str(dt_col)
            
            values = [
                dt,
                f"{get_val(row, 'Open'):.2f}",
                f"{get_val(row, 'High'):.2f}",
                f"{get_val(row, 'Low'):.2f}",
                f"{get_val(row, 'Close'):.2f}",
                f"{int(get_val(row, 'Volume')):,}"
            ]
            self.data_tree.insert("", "end", values=values)

    def plot_chart(self, data, ticker):
        self.ax.clear()
        self.ax.set_facecolor("#1e1e1e")

        chart_type = self.chart_type_var.get()
        close_vals = data["Close"].values
        
        close = []
        for c in close_vals:
            if hasattr(c, 'item'):
                close.append(c.item())
            else:
                close.append(c)
        
        dates = range(len(close))

        if chart_type == "line":
            self.ax.plot(dates, close, color="#00ff88", linewidth=1.5, label="Close")
            self.ax.fill_between(dates, close, alpha=0.3, color="#00ff88")
        else:
            ohlc = data[["Open", "High", "Low", "Close"]].values
            for i, (open_price, high, low, close_price) in enumerate(ohlc):
                open_p = open_price.item() if hasattr(open_price, 'item') else open_price
                high_p = high.item() if hasattr(high, 'item') else high
                low_p = low.item() if hasattr(low, 'item') else low
                close_p = close_price.item() if hasattr(close_price, 'item') else close_price
                
                color = "#00ff88" if close_p >= open_p else "#ff4444"
                self.ax.plot([i, i], [low_p, high_p], color=color, linewidth=1)
                body_bottom = min(open_p, close_p)
                body_height = abs(close_p - open_p)
                self.ax.add_patch(Rectangle((i - 0.3, body_bottom), 0.6, body_height, color=color))

        self.ax.set_title(f"{ticker} - {self.interval_combo.get()} Chart", color="#ffffff", fontsize=12)
        self.ax.set_xlabel("Time", color="#888888")
        self.ax.set_ylabel("Price", color="#888888")
        self.ax.tick_params(colors="#888888")
        for spine in self.ax.spines.values():
            spine.set_color("#444444")
        self.ax.grid(True, alpha=0.2, color="#444444")

        self.fig.tight_layout()
        self.canvas.draw()

    def toggle_live(self):
        if not self.live_refresh:
            if not self.current_ticker:
                messagebox.showwarning("No Data", "Please analyze a stock first")
                return
            self.live_refresh = True
            self.stop_refresh.clear()
            self.live_btn.config(text="Live: ON", bg="#00ff88", fg="#000000")
            self.refresh_thread = threading.Thread(target=self.live_refresh_loop, daemon=True)
            self.refresh_thread.start()
        else:
            self.live_refresh = False
            self.stop_refresh.set()
            self.live_btn.config(text="Live: OFF", bg="#2d2d2d", fg="#ffffff")

    def live_refresh_loop(self):
        while not self.stop_refresh.is_set():
            self.root.after(0, self.analyze_stock)
            time.sleep(30)

    def load_watchlist(self):
        if os.path.exists(WATCHLIST_FILE):
            try:
                with open(WATCHLIST_FILE, "r") as f:
                    self.watchlist = json.load(f)
            except:
                self.watchlist = []

    def save_watchlist(self):
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(self.watchlist, f)

    def update_watchlist_display(self):
        if hasattr(self, 'watchlistbox'):
            self.watchlistbox.delete(0, tk.END)
            for ticker in self.watchlist:
                self.watchlistbox.insert(tk.END, ticker)

    def add_to_watchlist(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Input Error", "Enter a ticker to add")
            return
        if ticker not in self.watchlist:
            self.watchlist.append(ticker)
            self.save_watchlist()
            self.update_watchlist_display()

    def remove_from_watchlist(self):
        if hasattr(self, 'watchlistbox'):
            selection = self.watchlistbox.curselection()
            if selection:
                ticker = self.watchlistbox.get(selection[0])
                self.watchlist.remove(ticker)
                self.save_watchlist()
                self.update_watchlist_display()

    def load_from_watchlist(self, event):
        selection = self.watchlistbox.curselection()
        if selection:
            ticker = self.watchlistbox.get(selection[0])
            self.ticker_entry.delete(0, tk.END)
            self.ticker_entry.insert(0, ticker)
            self.analyze_stock()

    def on_closing(self):
        if self.live_refresh:
            self.stop_refresh.set()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = StockAnalyzerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
