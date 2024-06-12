from flask import Flask, request, jsonify
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np

app = Flask(__name__)

@app.route('/backtest', methods=['POST'])
def backtest():
    data = request.json
    result = back_test(data)
    return jsonify(result)

def get_stock_origintime(code):
    stock_data = []
    url = "https://fchart.stock.naver.com/sise.nhn?symbol={}&timeframe=day&count=1&requestType=0".format(code)
    html = requests.get(url).text
    soup = BeautifulSoup(html, "xml")
    origintime = soup.select_one("chartdata")['origintime']
    return origintime

def get_stock_data(code, from_date, to_date):
    from_date = str(from_date)
    to_date = str(to_date)
    count = (datetime.today() - datetime.strptime(from_date, "%Y%m%d")).days + 1

    stock_data = []
    url = "https://fchart.stock.naver.com/sise.nhn?symbol={}&timeframe=day&count={}&requestType=0".format(code, count)
    html = requests.get(url).text
    soup = BeautifulSoup(html, "xml")
    data = soup.findAll('item')
    for row in data:
        daily_history = re.findall(r"[-+]?\d*\.\d+|\d+", str(row))
        if int(daily_history[0]) >= int(from_date) and int(daily_history[0]) <= int(to_date):
            daily_history[0] = datetime.strptime(daily_history[0], "%Y%m%d")
            daily_history[1] = float(daily_history[1])
            daily_history[2] = float(daily_history[2])
            daily_history[3] = float(daily_history[3])
            daily_history[4] = float(daily_history[4])
            daily_history[5] = float(daily_history[5])
            stock_data.append(daily_history)

    df = pd.DataFrame(stock_data, columns=['date', 'price', 'high', 'low', 'close', 'vol'])
    df.set_index(keys='date', inplace=True)
    return df

def buy_stock(money, stock_price, last_stock_num, stock_rate):
    if stock_price == 0:
        return money, 0, 0

    stock_num = money * stock_rate // stock_price
    stock_money = stock_num * stock_price
    if last_stock_num < stock_num:
        fee = 0.00015 # 매수 수수료
    else:
        fee = 0.0023 # 매도 수수료
    buy_sell_fee = abs(last_stock_num - stock_num) * stock_price * fee
    while stock_num > 0 and money < (stock_money + buy_sell_fee):
        stock_num -= 1
        stock_money = stock_num * stock_price
        buy_sell_fee = abs(last_stock_num - stock_num) * stock_price * fee

    money -= (stock_money + buy_sell_fee)
    return money, stock_num, stock_money

def buy_stock_more(money, stock_price, last_stock_num, stock_rate):
    if stock_price == 0:
        return money, 0, 0

    stock_num = money * stock_rate // stock_price
    stock_money = stock_num * stock_price
    if last_stock_num < stock_num:
        fee = 0.001 # 매수 수수료
    else:
        fee = 0.001 # 매도 수수료
    buy_sell_fee = stock_num * stock_price * fee
    while stock_num > 0 and money < (stock_money + buy_sell_fee):
        stock_num -= 1
        stock_money = stock_num * stock_price
        buy_sell_fee = stock_num * stock_price * fee
    money -= (stock_money + buy_sell_fee)

    stock_num = stock_num + last_stock_num
    stock_money = stock_num * stock_price

    return money, stock_num, stock_money

def get_ratio(names, prices, ratios):
    total_ratio = 0
    new_ratios = []
    for name in names:
        if prices[name] > 0:
            total_ratio += ratios[names.index(name)]
            new_ratios.append(ratios[names.index(name)])
        else:
            new_ratios.append(0)

    for i in range(len(new_ratios)):
        new_ratios[i] = round(new_ratios[i] * 1 / total_ratio, 2)

    return new_ratios

def get_month_end_data(df):
    df.index = pd.to_datetime(df.index)
    return df.resample('ME').last()

def calculate_sharpe_ratio_and_std(df, risk_free_rate=0.03):
    df.index = pd.to_datetime(df.index)
    df['monthly_return'] = df['backtest'].pct_change().dropna()

    monthly_std_dev = df['monthly_return'].std()

    cumulative_return = df['backtest'].iloc[-1] / df['backtest'].iloc[0] - 1
    total_period_years = (df.index[-1] - df.index[0]).days / 365.25
    annual_return = (1 + cumulative_return) ** (1 / total_period_years) - 1
    annual_std_dev = monthly_std_dev * np.sqrt(12)
    sharpe_ratio = (annual_return - risk_free_rate) / annual_std_dev

    return round(sharpe_ratio, 2), round(annual_std_dev * 100, 2), round(annual_return, 2)

def back_test_portfolio(money: int, interval: int, start_day: str, end_day: str, stock_list, start_from_latest_stock: str):
    total_invest_money = money

    stock_code = []
    stock_name = []
    stock_ratio = []

    for sss in stock_list:
        stock_code.append(sss[0])
        stock_name.append(sss[1])
        stock_ratio.append(sss[2])

    if sum(stock_ratio) > 1:
        print("ERROR!!! sum of ratio is over than 1.0")
        return

    first_date = 0
    for i in stock_code:
        org_time = get_stock_origintime(i)
        if start_from_latest_stock == "true":
            if first_date == 0 or first_date < org_time:
                first_date = org_time
        else:
            if first_date == 0 or first_date > org_time:
                first_date = org_time

    if first_date > start_day:
        start_day = first_date

    start_date = datetime.strptime(start_day, '%Y%m%d')
    cal_days = (datetime.strptime(end_day, "%Y%m%d") - start_date).days

    df = pd.DataFrame()

    for i in range(len(stock_code)):
        df_close = get_stock_data(stock_code[i], start_day, end_day)['close']
        df_close = df_close.rename(stock_name[i])
        df_close.index = pd.to_datetime(df_close.index)
        df_close = get_month_end_data(df_close)
        df = pd.merge(df, df_close, how='outer', left_index=True, right_index=True)

    df.columns = stock_name
    df.fillna(0, inplace=True)

    if start_from_latest_stock == "true":
        latest_start_date = max(pd.to_datetime([get_stock_origintime(code) for code in stock_code]))
        df = df[df.index >= latest_start_date]

    rebalanceing_date_list = []
    while start_date <= df.index[-1]:
        temp_date = start_date
        while temp_date not in df.index and temp_date < df.index[-1]:
            temp_date += timedelta(days=1)
        rebalanceing_date_list.append(temp_date)
        start_date += relativedelta(months=interval)

    backtest_index = []
    backtest_data = []

    etf_num = {etf: 0 for etf in stock_name}
    prices = {etf: 0 for etf in stock_name}
    etf_money = {etf: 0 for etf in stock_name}

    date_idx = 0
    for each in df.index:
        rebalnace_day = False
        if date_idx < len(rebalanceing_date_list) and each == rebalanceing_date_list[date_idx] and interval > 0:
            if (date_idx) % interval == 0:
                rebalnace_day = True
            date_idx += 1

        for stock in stock_name:
            prices[stock] = df[stock][each]
            if rebalnace_day is True:
                money += etf_num[stock] * prices[stock]

        recal_ratio = get_ratio(stock_name, prices, stock_ratio)

        total = 0
        cal = 0

        for stock in stock_name:
            try:
                if rebalnace_day is True:
                    money, etf_num[stock], etf_money[stock] = buy_stock(money, prices[stock], etf_num[stock], recal_ratio[stock_name.index(stock)]/((1-cal) if cal < 1 else 1))
                else:
                    money, etf_num[stock], etf_money[stock] = buy_stock_more(money, prices[stock], etf_num[stock], recal_ratio[stock_name.index(stock)]/((1-cal) if cal < 1 else 1))
            except Exception as e:
                print(e)

            if etf_num[stock] > 0:
                total += etf_money[stock]
                cal += recal_ratio[stock_name.index(stock)]

        total += money
        backtest_index.append(each)
        backtest_data.append(int(total)/total_invest_money)

    backtest_df = pd.DataFrame(backtest_data, index=backtest_index, columns=['backtest'])

    final_df = pd.concat([df, backtest_df], axis=1)

    for stock in stock_name:
        for pr in final_df[stock]:
            if pr > 0:
                final_df[stock] = final_df[stock] / pr
                break

    final_df.index = final_df.index.astype(str)
    final_df_dict = final_df.to_dict()

    sharpe_ratio, annual_std_dev, annual_return = calculate_sharpe_ratio_and_std(final_df)

    return final_df, final_df_dict, sharpe_ratio, annual_std_dev, annual_return, total




def calculate_mdd(df):
    df['cumulative_max'] = df['backtest'].cummax()
    df['drawdown'] = df['backtest'] / df['cumulative_max'] - 1
    mdd = df['drawdown'].min()
    return mdd


def back_test(stock_info):  

    portfolio = stock_info['portfolio']
    start_from_latest_stock = stock_info['start_from_latest_stock']

    stock_list = portfolio['stock_list']
    balance = portfolio['balance']
    interval = portfolio['interval_month']
    start_date = portfolio['start_date']
    end_date = portfolio['end_date']

    final_df, final_df_dict, sharpe_ratio, annual_std_dev, annual_return, total_balance = back_test_portfolio(balance, interval, start_date, end_date, stock_list, start_from_latest_stock)

    
    # MDD 계산
    mdd = calculate_mdd(final_df)
    
    result = {'portfolio': final_df_dict, 'sharpe_ratio': sharpe_ratio, 'standard_deviation': annual_std_dev, 'annual_return': annual_return, 'total_balance': total_balance, 'mdd': mdd}


    
    return result

if __name__ == '__main__':
    app.run(debug=True)

