#%%
'''
https://j-smallworld.tistory.com/15
리밸런싱 백테스트
'''
import requests
import json 
import pandas as pd 
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import matplotlib as rc
rc.use('TkAgg')
import matplotlib.pyplot as plt
import platform
if platform.system() == 'Darwin': #맥
    plt.rcParams['font.family'] ='AppleGothic'
elif platform.system() == 'Windows': #윈도우
    plt.rcParams['font.family'] = 'Malgun Gothic'
elif platform.system() == 'Linux': #리눅스
    plt.rcParams['font.family'] = 'Malgun Gothic' 
plt.rcParams['axes.unicode_minus'] = False #한글 폰트 사용시 마이너스 폰트 깨짐 해결



# 종목코드별 상장일
def get_stock_origintime(code): 
    """ 
    Naver 금융 데이터 페이지를 크롤링하여 특정 종목의 상장일 획득
    :param code: 종목 코드 
    :return: 종목코드 시작일자(origintime) 
    """ 
    
    stock_data = []
    url = "https://fchart.stock.naver.com/sise.nhn?symbol={}&timeframe=day&count=1&requestType=0".format(code) 
    html = requests.get(url).text 
    soup = BeautifulSoup(html, "xml") 
    origintime = soup.select_one("chartdata")['origintime'] 
     
    return origintime


# 주가 데이터 조회
def get_stock_data(code, from_date, to_date):
    """
    Naver 금융 데이터 페이지를 크롤링하여 주가 기록 조회
    :param code: 종목 코드
    :param from_date: 조회 시작일자
    :param to_date: 조회 종료일자
    :return: 해당 종목 코드의 일자, 시가, 고가, 저가, 종가, 거래량 데이터프레임
    """

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


# 리밸런싱 하는 경우
def buy_stock(money, stock_price, last_stock_num, stock_rate):
    '''
    총 평가금액을 기준으로 설정 비율대로 리밸런싱 수행
    '''
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


# 월 적립만 하는 경우
def buy_stock_more(money, stock_price, last_stock_num, stock_rate):
    '''
    StockInfo.json 에서 interval_month 을 0으로 설정하는 경우
    기존 구매한 종목에 대해서는 리밸런싱 하지 않고
    추가 투자 금액만 가지고 비율대로 매수만 수행
    '''
    if stock_price == 0:
        return money, 0, 0

    stock_num = money * stock_rate // stock_price
    stock_money = stock_num * stock_price
    if last_stock_num < stock_num:
        fee = 0.00015 # 매수 수수료
    else:
        fee = 0.0023 # 매도 수수료
    buy_sell_fee = stock_num * stock_price * fee
    while stock_num > 0 and money < (stock_money + buy_sell_fee):
        stock_num -= 1
        stock_money = stock_num * stock_price
        buy_sell_fee = stock_num * stock_price * fee
    money -= (stock_money + buy_sell_fee)

    # 추가 매수한 만큼 더해준다
    stock_num = stock_num + last_stock_num
    stock_money = stock_num * stock_price

    return money, stock_num, stock_money


def get_ratio(names, prices, ratios):
    '''
    상장일이 모두 다르기 때문에 특정 기간 동안에는 일부 종목이 매수되지 않게 된다.
    이때는 상장 되어있는 종목으로만 구성하여 자산 비율을 재계산 한다.
    예) 4개의 종목을 각각 25%씩 구성 -> 백테스팅 기간 중 앞에 1년은 두 개 종목만 상장되어 있는 상태.
       상장된 두 개의 종목 구성 비율을 50%로 설정하여 현금을 최대한 투자에 사용하도록 함.
    
    현금이 남더라도 기존 설정 비율대로만 매수하도록 테스트 할 경우, 이 함수 맨 마지막 한 줄을 다음과 같이 변경하여 사용
    return new_ratios --> return ratios
    '''
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


def back_test(money: int, interval: int, start_day: str, end_day: str, stock_list, monthly_amount: int, start_from_latest_stock: str):

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

    # 백테스팅 시작 날짜가 주식 리스트 중 가장 첫 상장일보다 빠른 경우 보정
    if first_date > start_day:
        start_day = first_date
    
    start_date = datetime.strptime(start_day, '%Y%m%d')  # 조회시작일

    cal_days = (datetime.strptime(end_day, "%Y%m%d") - start_date).days
    
    # stock_code = ['360750', '133690', '381170', '309230', '381180'] 
    # stock_name = ['TIGER 미국S&P500', 'TIGER 미국나스닥100', 'TIGER 미국테크TOP10 INDXX', 'KINDEX 미국WideMoat가치주', 'TIGER 미국필라델피아반도체나스닥'] 

    df = pd.DataFrame() 

    for i in range(len(stock_code)): 
        df_close = get_stock_data(stock_code[i], start_day, end_day)['close']
        df_close = df_close.rename(stock_name[i])  # 열 이름을 종목 이름으로 변경
        df = pd.merge(df, df_close, how='outer', left_index=True, right_index=True)


    df.columns = stock_name
    df.fillna(0, inplace=True)
    #print(df)

    # 리밸런싱 날짜 리스트 저장
    rebalanceing_date_list = []
    while start_date <= df.index[-1]:
        temp_date = start_date
        while temp_date not in df.index and temp_date < df.index[-1]:
            temp_date += timedelta(days=1)  # 영업일이 아닐 경우 1일씩 증가.
        rebalanceing_date_list.append(temp_date)
        start_date += relativedelta(months=1)  # interval 개월씩 증가.


    # backtest_df = pd.DataFrame()  # 백테스트를 위한 데이터프레임
    backtest_index = []
    backtest_data = []

    #{ticker: False for ticker in tickers}
    etf_num = {etf: 0 for etf in stock_name} # 구매한 ETF 개수
    prices = {etf: 0 for etf in stock_name} # 현재가
    etf_money = {etf: 0 for etf in stock_name} # 평가금액


    date_idx = 0
    for each in df.index:
        rebalnace_day = False
        if date_idx < len(rebalanceing_date_list) and each == rebalanceing_date_list[date_idx] and interval > 0:
            if (date_idx)%interval == 0:
                rebalnace_day = True
            date_idx += 1

        for stock in stock_name:
            prices[stock] = df[stock][each]
            # 리밸런싱 하는 달에는 총 금액 대비 비율 계산을 위해 보유 종목 매도 처리
            if rebalnace_day is True:
                money += etf_num[stock] * prices[stock]

        if date_idx < len(rebalanceing_date_list) and each == rebalanceing_date_list[date_idx] and date_idx > 0:
            money += monthly_amount
            # 총 투자금 대비 수익률 계산을 위해 투자금만 별도 관리
            total_invest_money += monthly_amount

        recal_ratio = get_ratio(stock_name, prices, stock_ratio)

        total = 0
        cal = 0

        for stock in stock_name:
            # 종목 매입
            try:
                if rebalnace_day is True:
                    # 리밸런싱 하는 경우, 전체 금액을 기준으로 투자 비율대로 매수
                    money, etf_num[stock], etf_money[stock] = buy_stock(money, prices[stock], etf_num[stock], recal_ratio[stock_name.index(stock)]/((1-cal) if cal < 1 else 1))
                else:
                    # 추가 매수만 하는 경우, 월 적립금을 기준으로 투자 비율대로 나누어 매수
                    money, etf_num[stock], etf_money[stock] = buy_stock_more(money, prices[stock], etf_num[stock], recal_ratio[stock_name.index(stock)]/((1-cal) if cal < 1 else 1))
            except Exception as e:
                print(e)

            if etf_num[stock] > 0:
                total += etf_money[stock] 
                cal += recal_ratio[stock_name.index(stock)]

        total += money
        backtest_index.append(each)
        backtest_data.append(int(total)/total_invest_money)
        # backtest_df[each] = [int(total)]


    # 행열을 바꿈
    backtest_df = pd.DataFrame(backtest_data, index=backtest_index, columns=['backtest'])
    # backtest_df = backtest_df.transpose()
    # backtest_df.columns = ['backtest', ]

    # 백테스트 결과 출력
    print("Total balance : {:>10}".format(str(int(total))))
    print("Investing Cash: {:>10}".format(str(total_invest_money)))
    print(backtest_df)

    # 최종 데이터 프레임, 3개의 지표와 백테스트 결과
    final_df = pd.concat([df, backtest_df], axis=1)

    # 시작점을 1로 통일함.
    for stock in stock_name:
        for pr in final_df[stock]:
            if pr > 0:
                final_df[stock] = final_df[stock] / pr
                break


   #final_df['backtest'] = final_df['backtest'] / total_invest_money

    return final_df





'''
Main
'''

# test_json = {'stock_list': stock_list, 'balance': balance, 'interval': interval, 'start_date': start_date, 'end_date': end_date}
# print(test_json)

stock_file_path = "./StockInfo.json"
try:
    with open(stock_file_path, "r", encoding="utf-8") as json_file:
        stock_info = json.load(json_file)
        # 테스트할 포트폴리오 개수
        num_of_portfolio = stock_info['num_of_portfolio']
        # 가장 최근에 상장한 날짜부터 계산할 지 여부: "true" or "false"
        # "false" 인 경우에는 가장 처음에 상장한 날짜부터 테스트
        start_from_latest_stock = stock_info['start_from_latest_stock']
        portfolio_list = []
        df_list =[]

        plt.rcParams["figure.figsize"] = (8,4*num_of_portfolio)
        plt.subplots(constrained_layout=True)

        for i in range(num_of_portfolio):
            # 테스트 할 포트폴리오 별 셋팅 정보 확인
            portfolio_list.append(stock_info['portfolio_' + str(i)])
            p = portfolio_list[i]
            stock_list = p['stock_list']
            balance = p['balance']
            interval = p['interval_month']
            start_date = p['start_date']
            end_date = p['end_date']
            monthly_amount = p['monthly_amount']

            # backtest 수행
            final_df = back_test(balance, interval, start_date, end_date, stock_list, monthly_amount, start_from_latest_stock)
        
            # 그래프 출력
            bbox = dict( ## 텍스트 박스 스타일 지정
                boxstyle='square', # 박스 모양
                facecolor='white', # 박스 배경색
            )

            plt.subplot(num_of_portfolio, 1, i + 1)

            plt.title("Portfolio " + str(i) + "(rebalancing interval(month):" + str(interval) + ")")

            # 백테스팅 결과 표시 (점선)
            # 백테스팅 수익률(최종평가액/투자원금)은 label에 표시
            height = final_df['backtest'][-1]
            plt.plot(final_df['backtest'].index, final_df['backtest'], label='Backtest (%.2f)'%height)      
            #plt.text(final_df['backtest'].index[-1], height, '%.2f' %height, ha='center', va='bottom', size = 8, bbox = bbox)

            stock_name = []
            for sss in stock_list:
                stock_name.append(sss[1])

            # 개별 종목 별 그래프 표시 (실선)
            for stock in stock_name:
                height = final_df[stock][-1]

                # 각 종목 별 수익률(최종평가액/투자원금)는 label에 표시
                plt.plot(final_df[stock].index, final_df[stock], label=stock+"(%.2f)"%height, linestyle='--', alpha=0.3)
                #plt.text(final_df[stock].index[-1], height, '%.2f' %height, ha='center', va='bottom', size = 6)
                # height = final_df[stock][-1]
                # plt.text(final_df[stock].index[-1], height, '%.1f' %height, ha='center', va='bottom', size = 8, bbox = bbox)
      
            plt.ylabel("수익률(최종평가액/투자원금)")
            plt.xlabel("날짜")
            plt.legend(loc='upper left')
            
            plt.grid(True)
        
        # 그래프를 stock_backtest.png 이미지 파일로 저장
        plt.savefig("stock_backtest.png")
        #plt.show()

except Exception as e:
    print("Exception:", e)

# %%
