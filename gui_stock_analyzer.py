import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import json
import os
import threading
from datetime import datetime, timedelta
import time

WATCHLIST_FILE = "watchlist.json"

class StockAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Analyzer GUI")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e1e")

        self.watchlist = []
        self.current_data = None
        self.current_ticker = None
        self.live_refresh = False
        self.refresh_thread = None
        self.stop_refresh = threading.Event()

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
        top_frame = ttk.Frame(self.root)
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

        self.analyze_btn = ttk.Button(top_frame, text="Analyze", command=self.analyze_stock)
        self.analyze_btn.pack(side="left", padx=10)

        self.live_btn = tk.Button(top_frame, text="Live: OFF", command=self.toggle_live, bg="#2d2d2d", fg="#ffffff", relief="raised")
        self.live_btn.pack(side="left", padx=5)

        self.chart_type_var = tk.StringVar(value="line")
        ttk.Radiobutton(top_frame, text="Line", variable=self.chart_type_var, value="line").pack(side="left", padx=5)
        ttk.Radiobutton(top_frame, text="Candle", variable=self.chart_type_var, value="candle").pack(side="left", padx=5)

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ttk.Label(left_frame, text="Stock Data", font=("Arial", 12, "bold")).pack(anchor="w")
        self.data_tree = ttk.Treeview(left_frame, show="headings", height=10)
        columns = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        self.data_tree["columns"] = columns
        for col in columns:
            self.data_tree.heading(col, text=col)
            self.data_tree.column(col, width=100, anchor="center")
        self.data_tree.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        right_frame = ttk.Frame(main_frame, width=200)
        right_frame.pack(side="right", fill="both", padx=(5, 0))
        right_frame.pack_propagate(False)

        ttk.Label(right_frame, text="Watchlist", font=("Arial", 12, "bold")).pack(anchor="w")

        self.watchlistbox = tk.Listbox(right_frame, bg="#2d2d2d", fg="#ffffff", selectbackground="#007acc")
        self.watchlistbox.pack(fill="both", expand=True, pady=5)
        self.watchlistbox.bind("<Double-Button-1>", self.load_from_watchlist)

        watchlist_btn_frame = ttk.Frame(right_frame)
        watchlist_btn_frame.pack(fill="x", pady=5)

        ttk.Button(watchlist_btn_frame, text="Add", command=self.add_to_watchlist).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(watchlist_btn_frame, text="Remove", command=self.remove_from_watchlist).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(watchlist_btn_frame, text="Clear", command=self.clear_watchlist).pack(side="left", fill="x", expand=True, padx=2)

        chart_frame = ttk.Frame(self.root)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ttk.Label(chart_frame, text="Chart", font=("Arial", 12, "bold")).pack(anchor="w")

        self.fig = Figure(figsize=(8, 4), facecolor="#1e1e1e")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#1e1e1e")
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", padx=10, pady=(0, 10))

    def analyze_stock(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Input Error", "Please enter a ticker symbol")
            return

        period = self.period_combo.get()
        interval = self.interval_combo.get()

        if self.interval_to_minutes(interval) * self.period_to_days(period) > 730 * 1440:
            messagebox.showwarning("Data Limit", "Selected period/interval combination exceeds data limits")
            return

        self.status_var.set(f"Downloading {ticker} data...")
        self.analyze_btn.config(state="disabled")

        try:
            data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)

            if data.empty:
                messagebox.showerror("Error", f"No data found for ticker '{ticker}'")
                self.status_var.set("Ready")
                self.analyze_btn.config(state="normal")
                return

            self.current_data = data
            self.current_ticker = ticker

            self.update_data_table(data)
            self.plot_chart(data, ticker)
            self.status_var.set(f"Loaded {ticker} - {len(data)} data points")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch data: {str(e)}")
            self.status_var.set("Error")

        self.analyze_btn.config(state="normal")

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
            if hasattr(dt_col, 'strftime'):
                dt = dt_col.strftime("%Y-%m-%d %H:%M")
            else:
                dt = str(dt_col)
            
            open_val = get_val(row, 'Open')
            high_val = get_val(row, 'High')
            low_val = get_val(row, 'Low')
            close_val = get_val(row, 'Close')
            volume_val = get_val(row, 'Volume')
            
            values = [
                dt,
                f"{open_val:.2f}",
                f"{high_val:.2f}",
                f"{low_val:.2f}",
                f"{close_val:.2f}",
                f"{int(volume_val):,}"
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
                color = "#00ff88" if close_price >= open_price else "#ff4444"
                self.ax.plot([i, i], [low, high], color=color, linewidth=1)
                body_bottom = min(open_price, close_price)
                body_height = abs(close_price - open_price)
                self.ax.add_patch(Rectangle((i - 0.3, body_bottom), 0.6, body_height, color=color))

        self.ax.set_title(f"{ticker} - {self.interval_combo.get()} Chart", color="#ffffff", fontsize=12)
        self.ax.set_xlabel("Time", color="#888888")
        self.ax.set_ylabel("Price", color="#888888")
        self.ax.tick_params(colors="#888888")
        self.ax.spines["bottom"].set_color("#444444")
        self.ax.spines["top"].set_color("#1e1e1e")
        self.ax.spines["left"].set_color("#444444")
        self.ax.spines["right"].set_color("#1e1e1e")
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
        selection = self.watchlistbox.curselection()
        if selection:
            ticker = self.watchlistbox.get(selection[0])
            self.watchlist.remove(ticker)
            self.save_watchlist()
            self.update_watchlist_display()

    def clear_watchlist(self):
        if messagebox.askyesno("Confirm", "Clear entire watchlist?"):
            self.watchlist = []
            self.save_watchlist()
            self.update_watchlist_display()

    def load_from_watchlist(self, event):
        selection = self.watchlistbox.curselection()
        if selection:
            ticker = self.watchlistbox.get(selection[0])
            self.ticker_entry.delete(0, tk.END)
            self.ticker_entry.insert(0, ticker)
            self.analyze_stock()

    def interval_to_minutes(self, interval):
        mapping = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30, "60m": 60, "90m": 90, "1h": 60, "1d": 1440, "5d": 7200, "1wk": 10080, "1mo": 43200}
        return mapping.get(interval, 1)

    def period_to_days(self, period):
        mapping = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "ytd": 365, "max": 3650}
        return mapping.get(period, 60)

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
