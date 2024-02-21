#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 20:38:42 2023

@author: damodarbasyal
"""

#Importing necessary library
import numpy as np
import yfinance as yf
import math
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
import time, os

nytime=pytz.timezone('America/New_York')

def download_data(ticker, period='1mo', interval='5m'):
    """Download data from yahoo_finance"""
    data=yf.download(ticker,period=period, interval=interval)
    data["Candle"]=np.where(data['Open']>data["Close"], "Red", "Green") #Here for simplicity, candle with same open and close value is considered as "Green"
    return data

def nadaraya_watson(src, h, mult):
    """Function to calculate upper band and lower band of Nadaraya_Watson_Envelope"""
    y = []
    #.................#
    upper_band = []
    lower_band = []
    #....................#
    sum_e = 0
    for i in range(len(src)):
        sum = 0
        sumw = 0   
        for j in range(len(src)):
            w = math.exp(-(math.pow(i-j,2)/(h*h*2)))
            sum += src[j]*w
            sumw += w
        y2 = sum/sumw
        sum_e += abs(src[i] - y2)
        y.insert(i,y2)
    mae = sum_e/len(src)*mult
    for i  in range(len(src)):
        upper_band.insert(i,y[i]+mae)
        lower_band.insert(i,y[i]-mae)
    return upper_band, lower_band

def rsi(df, n):
    """Function to calculate RSI"""
    delta=df["Close"].diff().dropna()
    u=delta*0
    d=u.copy()
    u[delta>0]=delta[delta>0]
    d[delta<0]=-delta[delta<0]
    u[u.index[n-1]]=np.mean(u[:n])
    u=u.drop(u.index[:(n-1)])
    d[d.index[n-1]]=np.mean(d[:n])
    d=d.drop(d.index[:(n-1)])
    rs=u.ewm(com=n,min_periods=n).mean()/d.ewm(com=n,min_periods=n).mean()
    return 100-100/(1+rs)

def atr_stop_loss_finder(source, length=14, multiplier=0.5):
    atr=source['High']-source['Low']
    atr_smoothed=atr.rolling(length).mean()
    atr_stop_loss_long=source["Low"]-atr_smoothed*multiplier
    atr_stop_loss_short=source["High"]+atr_smoothed*multiplier
    return atr_stop_loss_long, atr_stop_loss_short

def plot_nadaraya_watson(data):
    """Function to plot Nadaraya_Watson_Envelope"""
    plt.figure(figsize=(18,8))
    plt.plot(data["Upper_Band"].values, color= 'green', linestyle='--', linewidth=2) 
    plt.plot(data["Lower_Band"].values, color= 'red', linestyle='--', linewidth=2)
    plt.plot(data["Close"].values, color= 'blue', label= 'Data')
    plt.show()
    
def round_by_five(time):
    if time.second==0 and time.microsecond==0 and time.minute%5==0:
        return time
    minutes_by_five=time.minute//5
    #Get the difference in times
    diff=(minutes_by_five+1)*5-time.minute
    start_time=(time+timedelta(minutes=diff)).replace(second=0, microsecond=0)
    return start_time

def buy_sell(ticker, candle, price, quantity, signal, stop_loss, take_profit):
    today_date=datetime.today().strftime('%Y-%m-%d')
    if not os.path.exists("backtest/transaction/NSE/{}/transaction.csv".format(today_date)):
        if not os.path.exists("backtest/transaction/NSE/{}".format(today_date)):
            os.makedirs("backtest/transaction/NSE/{}".format(today_date))
        test_df=pd.DataFrame(columns=["Ticker","Datetime","Price","Quantity","Action","Stop_Loss","Take_Profit"])
        test_df.to_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date))
    
    transaction_df=pd.read_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date),index_col=0)
    transaction_df=transaction_df.reset_index(drop=True)
    position=transaction_df.loc[transaction_df['Ticker']==ticker]["Quantity"].sum()
    if position >0 and signal=='Long':
        update_sl_tp(ticker, stop_loss, take_profit)
        print("Already in LONG position. Stop_Loss and Take_Profit updated successfully!")
        print("---------------------------------------------------------------------------")
        return
    elif position <0 and signal=='Short':
        update_sl_tp(ticker, stop_loss, take_profit)
        print("Already in SHORT position. Stop_Loss and Take_Profit updated successfully!")
        print("---------------------------------------------------------------------------")
        return
    else:
        transaction_df=pd.concat([transaction_df,pd.DataFrame([[ticker, candle, price, quantity, signal, stop_loss, take_profit]],columns=["Ticker","Datetime","Price","Quantity","Action","Stop_Loss","Take_Profit"])],ignore_index=True)
        transaction_df.to_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date))

def update_sl_tp(ticker, stop_loss, take_profit):
    try:
        today_date=datetime.today().strftime('%Y-%m-%d')
        transaction_df=pd.read_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date),index_col=0)
        transaction_df=transaction_df.reset_index(drop=True)
        pos=transaction_df.loc[transaction_df['Ticker']==ticker]
        pos.loc[pos.index[-1],'Stop_Loss']=stop_loss
        pos.loc[pos.index[-1],'Take_Profit']=take_profit
        transaction_df.loc[pos.index, 'Stop_Loss']=pos['Stop_Loss']
        transaction_df.loc[pos.index, 'Take_Profit']=pos['Take_Profit']
        transaction_df.to_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date))
    except:
        print("Error in updating Stop_Loss/Take_Profit!")

def check_sl_tp(ticker,watch):
    try:
        today_date=datetime.today().strftime('%Y-%m-%d')
        if os.path.exists("backtest/transaction/{}/transaction.csv".format(today_date)):
            transaction_df=pd.read_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date),index_col=0)
            transaction_df=transaction_df.reset_index(drop=True)
            position=transaction_df.loc[transaction_df['Ticker']==ticker]["Quantity"].sum()
            if position!=0:
                pos=transaction_df.loc[transaction_df['Ticker']==ticker]
                stop_loss_price=pos.loc[pos.index[-1],'Stop_Loss']
                take_profit=pos.loc[pos.index[-1],'Take_Profit']
                if position>0:
                    if watch['Low'].iloc[1]<stop_loss_price:
                        print("---------------------------------------------------------------------------")
                        print("Stop loss triggered for {} and position closed with SHORT position.".format(ticker))
                        print("\t Stop Loss Price: @ Rs {}".format(stop_loss_price))
                        print("\t Quantity: {}".format(abs(position)))
                        print("---------------------------------------------------------------------------")
                        buy_sell(ticker, watch.index[-1], stop_loss_price, -position, 'Stop_Loss', 0, 0)
                    elif watch['High'].iloc[1]>take_profit:
                        print("---------------------------------------------------------------------------")
                        print("Take_Profit triggered for {} and position closed with SHORT position.".format(ticker))
                        print("\t Take Profit Price: @ Rs {}".format(take_profit))
                        print("\t Quantity: {}".format(abs(position)))
                        print("---------------------------------------------------------------------------")
                        buy_sell(ticker, watch.index[-1], take_profit, -position, 'Take_Profit', 0, 0)
                    else:
                        pass
                elif position<0:
                    if watch['High'].iloc[1]>stop_loss_price:
                        print("---------------------------------------------------------------------------")
                        print("Stop loss triggered for {} and position closed with LONG position.".format(ticker))
                        print("\t Stop Loss Price: @ Rs {}".format(stop_loss_price))
                        print("\t Quantity: {}".format(abs(position)))
                        buy_sell(ticker, watch.index[-1], stop_loss_price, -position, 'Stop_Loss', 0, 0)
                        print("---------------------------------------------------------------------------")
                    elif watch['Low'].iloc[1]<take_profit:
                        print("---------------------------------------------------------------------------")
                        print("Take_Profit triggered for {} and position closed with LONG position.".format(ticker))
                        print("\t Take Profit Price: @ Rs {}".format(take_profit))
                        print("\t Quantity: {}".format(abs(position)))
                        print("---------------------------------------------------------------------------")
                        buy_sell(ticker, watch.index[-1], take_profit, -position, 'Take_Profit', 0, 0)
                    else:
                        pass
                else:
                    pass
            else:
                pass
    except:
        print("Error in checking sl_tp function!")

def calculate_pl(ticker, watch):
    try:
        today_date=datetime.today().strftime('%Y-%m-%d')
        if os.path.exists("backtest/transaction/NSE/{}/transaction.csv".format(today_date)):
            if os.path.exists("backtest/transaction/NSE/{}/pl_position.csv".format(today_date)):
                pl_df=pd.read_csv("backtest/transaction/NSE/{}/pl_position.csv".format(today_date),index_col=0)
                pl_df=pl_df.reset_index(drop=True)
                position=pl_df.loc[pl_df['Ticker']==ticker]["Quantity"].sum()
                if position!=0:
                    candle, price=watch.index[-1],watch['Close'].iloc[1]
                    pl_df=pd.concat([pl_df,pd.DataFrame([[ticker, candle, price, -position, "Forced_Closed", 0, 0]],columns=["Ticker","Datetime","Price","Quantity","Action","Stop_Loss","Take_Profit"])],ignore_index=True)
                    pl_df["Profit_Loss"]=pl_df["Price"]*pl_df["Quantity"]*-1
                    pl_df.to_csv("backtest/transaction/NSE/{}/pl_position.csv".format(today_date))
    except:
        print("Error in calculating Profit/Loss!")

def pl_display():
    try:
        today_date=datetime.today().strftime('%Y-%m-%d')
        pl_df=pd.read_csv("backtest/transaction/NSE/{}/pl_position.csv".format(today_date),index_col=0)
        pl_df=pl_df.reset_index(drop=True)
        pl_ticker=pl_df.groupby('Ticker')["Profit_Loss"].sum().reset_index(name ='Profit/Loss Amount')
        print("---------------------------------------------------------------------------")
        print(pl_ticker)
        print("---------------------------------------------------------------------------")
        print("Today's total profit/loss from trade is: Rs {}".format(pl_ticker["Profit/Loss Amount"].sum()))
        print("---------------------------------------------------------------------------")
    except:
        print("Error in calculating tickerwise profit!")
                    
    
def main(tickers,capital):
    today_date=datetime.today().strftime('%Y-%m-%d')
    #This will copy transaction data to pl_df first so that update in transaction_df will be reflected
    if os.path.exists("backtest/transaction/NSE/{}/transaction.csv".format(today_date)):
        pl_df=pd.read_csv("backtest/transaction/NSE/{}/transaction.csv".format(today_date),index_col=0)
        pl_df=pl_df.reset_index(drop=True)
        pl_df.to_csv("backtest/transaction/NSE/{}/pl_position.csv".format(today_date))
    for ticker in tickers:
        print("Data download started at {}".format(datetime.now()))
        try:
            data=download_data(ticker)
            
            #Remove .NS from ticker. ".NS was required to download data of stock listed in NSE from yahoo finance.
            ticker=ticker.replace(".NS","")

            #Inserting Upper and Lower Band in "data" df
            data['Upper_Band'], data["Lower_Band"]=nadaraya_watson(src=data['Close'].values, h=8, mult=3)
            data["RSI"]=rsi(data, 14)
            data["Stop_Loss_Long"],data["Stop_Loss_Short"]=atr_stop_loss_finder(data,length=14, multiplier=0.5)
            duration=(datetime.now(nytime)-data.index[-1]).seconds
            if duration/60<5:
                #print("Last candle is not formed completely")
                data=data[:-1]
            
            #data.to_csv('{}'.format(ticker))
            #print("Last candle of {} is: {}".format(ticker, data.index[-1]))
            #Checking last two rows to find long and short signal 
            #-if low of candle is below lower bound and RSI is in oversold zone -> BUY; Take position if next candle is green
            #-if high of candle is above upper bound and RSI is in overbought zone -> SELL; Take position if next candle is red
            watch=data[-2:]
            
            quantity=int(capital/watch['Close'].iloc[1])
            #To test reliability of signal, I am making quantity is equal to 1 if price is above capital allocated
            if quantity==0:
                quantity=1
            if watch["Low"].iloc[0] < watch["Lower_Band"].iloc[0] and watch["RSI"].iloc[0]<30 and watch["Candle"].iloc[0]=="Red" and watch["Candle"].iloc[1]=="Green":
                take_profit=watch["Close"].iloc[1]+(watch["Close"].iloc[1]-watch["Stop_Loss_Long"].iloc[1])*1.5
                candle, price, stop_loss=watch.index[-1],watch['Close'].iloc[1],watch['Stop_Loss_Long'].iloc[1]
                print("Long for {} at closing price of last candle at time {}".format(ticker, str(datetime.now().time().strftime("%H:%M:%S"))))
                print("---------------------------------------------------------------------------")
                print("\t Buy: @ Rs {}".format(price))
                print("\t Stop Loss: @ Rs {}".format(stop_loss))
                print("\t Take Profit: @ Rs {}".format(take_profit))
                print("---------------------------------------------------------------------------")
                buy_sell(ticker, candle, price, quantity, 'Long', stop_loss, take_profit)
            elif watch["High"].iloc[0] > watch["Upper_Band"].iloc[0] and watch["RSI"].iloc[0]>70 and watch["Candle"].iloc[0]=="Green" and watch["Candle"].iloc[1]=="Red":
                take_profit=watch["Close"].iloc[1]-(watch["Stop_Loss_Short"].iloc[1]-watch["Close"].iloc[1])*1.5
                candle, price, stop_loss=watch.index[-1],watch['Close'].iloc[1],watch['Stop_Loss_Short'].iloc[1]
                print("Short for {} at closing price of last candle at time {}".format(ticker, str(datetime.now().time().strftime("%H:%M:%S"))))
                print("---------------------------------------------------------------------------")
                print("\t Sell: @ Rs {}".format(price))
                print("\t Stop Loss: @ Rs {}".format(stop_loss))
                print("\t Take Profit: @ Rs {}".format(take_profit))
                print("---------------------------------------------------------------------------")
                buy_sell(ticker, candle, price, -quantity, 'Short', stop_loss, take_profit)
            else:
                print("No LONG/SHORT signal found for {}!".format(ticker))
            
            #Check Stop_Loss and Take_Profit position. In real trading, it has be checked in real time
            check_sl_tp(ticker,watch)
            calculate_pl(ticker, watch)
            if not os.path.exists("backtest/price_data/NSE/{}".format(today_date)):
                os.makedirs("backtest/price_data/NSE/{}".format(today_date))
            data.to_csv("backtest/price_data/NSE/{}/{}.csv".format(today_date,ticker))
        
        except:
            print("Some error occured during download and processing. Skipping {} for now.".format(ticker))
    pl_display()
    #plot_nadaraya_watson(data) #This will plot the graph after removing last candle if it is not formed completely
    #time.sleep(2)

capital=5000
current_time=datetime.now(nytime)
print("Current time is {}".format(current_time))
start_time=round_by_five(current_time)

#Stock from NSE
tickers=["HDFCBANK.NS","RELIANCE.NS","ICICIBANK.NS","INFY.NS","ITC.NS","TCS.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","HINDUNILVR.NS","SBIN.NS","BHARTIARTL.NS","BAJFINANCE.NS","M&M.NS","MARUTI.NS","HCLTECH.NS","SUNPHARMA.NS","ASIANPAINT.NS","TITAN.NS","NTPC.NS","TATAMOTORS.NS","ULTRACEMCO.NS","POWERGRID.NS","TATASTEEL.NS","BAJAJFINSV.NS","NESTLEIND.NS","INDUSINDBK.NS","ONGC.NS","COALINDIA.NS","TECHM.NS","HINDALCO.NS","ADANIPORTS.NS","JSWSTEEL.NS","DRREDDY.NS","GRASIM.NS","CIPLA.NS","BAJAJ-AUTO.NS","HDFCLIFE.NS","ADANIENT.NS","SBILIFE.NS","TATACONSUM.NS","BRITANNIA.NS","WIPRO.NS","APOLLOHOSP.NS","LTIM.NS","EICHERMOT.NS","DIVISLAB.NS","HEROMOTOCO.NS","BPCL.NS","UPL.NS"]

#Stock from S&P 500
#tickers=["MSFT","AAPL","AMZN","NVDA","GOOG","ACN","PFE","QCOM","AMD","TSLA","NFLX"]

sleep_time=(start_time-datetime.now(nytime)).seconds
print("Will check after {} minutes {} seconds at {}\n".format(sleep_time//60, sleep_time%60, start_time))
while True:
    try:
        #sleep_time=(start_time-datetime.now(nytime)).seconds
        if datetime.now(nytime)>=start_time:
            main(tickers,capital)
            current_time=datetime.now(nytime)
            start_time=round_by_five(current_time)
            sleep_time=(start_time-datetime.now(nytime)).seconds
            print("Will check after {} minutes {} seconds at {}\n".format(sleep_time//60, sleep_time%60, start_time))
            time.sleep(1)
        else:
            #print("Will check after {} minutes {} seconds at {}".format(sleep_time//60, sleep_time%60, start_time))
            time.sleep(1)
    except:
        print("Some error occured! Will check again.")
"""This version has has issues with order placing. As long as signals are generated, it places the order. In next version,
program will not place order if the position is open for same order. This means if long signal is generated when there is already
long position, it will update the sl and tp and skip the order placement."""
