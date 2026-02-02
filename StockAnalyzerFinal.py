#This program is designed to analyze a stock ticker and an optional watchlist in the command line

import pandas as p       #used to manipulate the data
import yfinance as yf    #used to get historical data
import time 

#create empty list
watchlist = []

#def functions for menu and watchlist management
def display_menu():
    #Displays the main menu options
    print("\n~~M A I N    M E N U~~")
    main_menu = ["1. Scan a ticker", "2. View Watchlist", "3. Exit Program"]
    print('\n'.join(main_menu))

def update_watchlist(ticker):
    #Asks user if they want to add ticker to watchlist
    while True:
        add_to_list = input(f"Would you like to add {ticker} to your Watchlist? 'Y' or 'N'? ").upper()
        if add_to_list == 'Y':
            watchlist.append(ticker)
            print(f"{ticker} was added to your watchlist.")
            break
        elif add_to_list == 'N':
            print(f"{ticker} was not added to your watchlist.")
            break
        else:
            print("Please enter 'Y' or 'N'")

#Welcome to prog message
print("Welcome to the Stock Analyzer..")
time.sleep(2)

while True:
    display_menu()  # Call the menu function
    
    user_choice = input("\nClick '1' to scan a ticker,  '2' to View Watchlist,  or '3' to Quit Program: ")
    if user_choice.isdigit() and int(user_choice) in [1, 2, 3]: # Validates input
        user_input = int(user_choice)
    else:
        print("Invalid input. Please enter a number.")
        continue
    
    if user_input == 1:
        # Option 1: Scan a ticker
        while True:
            ticker = input("\nEnter a stock ticker (Like QQQ or TSLA) or type 'QUIT' to return to menu: ").strip().upper()
            
            if ticker == 'QUIT':
                break  # Exit inner loop, return to main menu
            
            print(f"Downloading {ticker} data..")
            data = yf.download(ticker, period='60d', interval='15m', auto_adjust=True) #auto adjust argument added to remove FutureWarning in output
            
            if data.empty: #type: ignore (checks if data returns empty for invalid ticker)
                print(f"'{ticker}' is not a valid ticker, no data found.")
            else:
                # Show only specific columns and last 10 rows
                print("\n--- Stock Data (Last Ten 15m Candles) ---")
                print(data[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10)) # type: ignore
                
                # Call the update_watchlist function
                update_watchlist(ticker)
                
            print(f"\nYour updated watchlist: {watchlist}")
    
    elif user_input == 2:
        # Option 2: View watchlist
        print("\n~~~ Y O U R  WATCHlist ~~~")
        if watchlist:
            for i, ticker in enumerate(watchlist, 1):
                print(f"{i}. {ticker}")
        if len(watchlist) >= 1:
            print(f"\nEnter the number of the ticker to remove it from your watchlist.")
            input_num = input("Ticker number to remove (or type 'BACK' to return to menu): ")
            if input_num.strip().upper() == 'BACK':
                continue
            elif input_num.isdigit() and 1 <= int(input_num) <= len(watchlist):
                removed_ticker = watchlist.pop(int(input_num) - 1)
                print(f"{removed_ticker} has been removed from your watchlist.")
                print(f"\nYour updated watchlist: {watchlist}")

            else:
                print("Invalid input. Please try again.")
        else:
            print("Your watchlist is empty.")
            
    
    elif user_input == 3:
        # Option 3: Exit program
        print("\nThank you for using Stock Analyzer!")
        print(f"Final watchlist: {watchlist}")
        break
    
    else:
        print("Invalid choice. Please enter 1, 2, or 3.")
