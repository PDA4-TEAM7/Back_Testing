import sys
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np

#주식 종목 코드(code)에 대해서 최초 상장일(origintime)을 가져옴 , 언제부터 백테스팅 돌릴지 체크
#네이버 금융 주식 데이터 사용
def get_stock_origintime(code):
    try:
        url = "https://fchart.stock.naver.com/sise.nhn?symbol={}&timeframe=day&count=1&requestType=0".format(code)
        html = requests.get(url).text
        soup = BeautifulSoup(html, "xml")
        origintime = soup.select_one("chartdata")['origintime']
        return origintime
    except Exception:
        raise ValueError(f"Stock code {code} not found")

#주식 종목 코드(code), 시작일, 종료일에 대해서 주식 data를 가져옴
#네이버 금융 주식 데이터 사용
def get_stock_data(code, from_date, to_date):
    try:
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
            #값이 설정한 기간 내에 존재한 다면
            if int(daily_history[0]) >= int(from_date) and int(daily_history[0]) <= int(to_date):
                daily_history[0] = datetime.strptime(daily_history[0], "%Y%m%d")
                daily_history[1] = float(daily_history[1])
                daily_history[2] = float(daily_history[2])
                daily_history[3] = float(daily_history[3])
                daily_history[4] = float(daily_history[4])
                daily_history[5] = float(daily_history[5])
                stock_data.append(daily_history)

        #pandas 이용을 위해 dataframe객체로 변환
        df = pd.DataFrame(stock_data, columns=['date', 'price', 'high', 'low', 'close', 'vol'])
        df.set_index(keys='date', inplace=True)
        return df
    except Exception:
        raise Exception(f"Failed to fetch data for stock code {code}")


#리밸런싱 용 코드. 비율에 맞춰 주식을 매수하거나 매도 처리
def buy_stock(money, stock_price, last_stock_num, stock_rate):
    if stock_price == 0:
        return money, 0, 0

    stock_num = money * stock_rate // stock_price
    stock_money = stock_num * stock_price
    if last_stock_num < stock_num:
        fee = 0.00015 # 매수 수수료, 토스 증권 기준
    else:
        fee = 0.000195 # 매도 수수료, 토스 증권 기준
    buy_sell_fee = abs(last_stock_num - stock_num) * stock_price * fee

    #돈 없으면 주식 갯수 조정
    while stock_num > 0 and money < (stock_money + buy_sell_fee):
        stock_num -= 1
        stock_money = stock_num * stock_price
        buy_sell_fee = abs(last_stock_num - stock_num) * stock_price * fee

    money -= (stock_money + buy_sell_fee)
    return money, stock_num, stock_money

#보유 자산에 현금 추가 되었을때 (안씀)
def buy_stock_more(money, stock_price, last_stock_num, stock_rate):
    if stock_price == 0:
        return money, 0, 0

    stock_num = money * stock_rate // stock_price
    stock_money = stock_num * stock_price
    if last_stock_num < stock_num:
        fee = 0.00015 # 매수 수수료 ,토스 증권 기준
    else:
        fee = 0.00195 # 매도 수수료, 토스 증권 기준
    buy_sell_fee = stock_num * stock_price * fee
    while stock_num > 0 and money < (stock_money + buy_sell_fee):
        stock_num -= 1
        stock_money = stock_num * stock_price
        buy_sell_fee = stock_num * stock_price * fee
    money -= (stock_money + buy_sell_fee)

    stock_num = stock_num + last_stock_num
    stock_money = stock_num * stock_price

    return money, stock_num, stock_money

#주식명,가격,비율을 받아서 가격에 대해 비율을 재 조정
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

#월말 데이터 추출(왜 인지 resample을 'M'말고 'ME'로 잡으라고 나옴)
def get_month_end_data(df):
    df.index = pd.to_datetime(df.index)
    return df.resample('ME').last()

#df와 무위험 이자율 데이터로 샤프비율,표준편차(std),연간 수익률 계산
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
        raise Exception("Sum of ratios is greater than 1.0")

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

#최대 낙폭 계산.
def calculate_mdd(df):
    df['cumulative_max'] = df['backtest'].cummax()
    df['drawdown'] = df['backtest'] / df['cumulative_max'] - 1
    mdd = df['drawdown'].min()
    return mdd

def back_test(stock_info):
    #포트폴리오 객체
    portfolio = stock_info['portfolio']
    
    # 백테스팅 시점 결정
    # 값이 true일 경우 가장 늦게 상장 된 주식의 상장일 기준으로 백테스팅 시작.
    # 값이 false일 경우 가장 먼저 상장 된 주식의 상장일 기준으로 백테스팅 시작.
    # 현재는 false이므로 먼저 상장된 기준으로 백테스팅하고, 그때 당시 안되있으면 반영이 안됨. (값 0 으로 처리)
    start_from_latest_stock = stock_info['start_from_latest_stock']

    #주식 목록 (종목코드,주식이름,포트폴리오 비율)
    stock_list = portfolio['stock_list']

    #초기 투자 총 금액
    balance = portfolio['balance']

    #리밸런싱 단위 (개월) ex) interval=1 은 1달마다 리밸런싱을 함을 의미합니다.
    interval = portfolio['interval_month']

    #백테스팅 시작일자
    start_date = portfolio['start_date']
    
    #백테스팅 끝일자
    end_date = portfolio['end_date']

    #백테스트 실행
    final_df, final_df_dict, sharpe_ratio, annual_std_dev, annual_return, total_balance = back_test_portfolio(balance, interval, start_date, end_date, stock_list, start_from_latest_stock)

    #최대 낙폭 계산
    mdd = calculate_mdd(final_df)

    result = {'portfolio': final_df_dict, 'sharpe_ratio': sharpe_ratio, 'standard_deviation': annual_std_dev, 'annual_return': annual_return, 'total_balance': total_balance, 'mdd': mdd}

    return result

if __name__ == '__main__':
    #json값 받아서 data사용
    input_json = sys.stdin.read()
    print(f"Received input: {input_json}", file=sys.stderr)  # 로그 추가
    data = json.loads(input_json)
    
    try:
        result = back_test(data)
        print(json.dumps(result, ensure_ascii=False))  # ensure_ascii=False 추가
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        print(f"Exception: {str(e)}", file=sys.stderr)  # 에러 로그 추가
