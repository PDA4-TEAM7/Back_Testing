# Back_Testing

## 설정

```
pip install requests beautifulsoup4 pandas matplotlib lxml flask numpy

- request : HTTP 요청
- beautifulsoup4 : HTML 및 XML 파싱
- pandas : 데이터 조작 및 분석
- matplotlib : 데이터 차트화
- lxml : 'beautifulsoup' 가 XML을 파싱하는 데에 사용
- flask : api 서버 생성
- numpy :

```

## 파일 실행
```
python stock_backtest.py
```
```
Method : POST
body : 
{
    "start_from_latest_stock": "false",
    "portfolio": {
        "stock_list": [
            ["360750", "TIGER 나스닥100", 0.25],
            ["133690", "TIGER 미국나스닥100", 0.25],
            ["309230", "KINDEX 미국WideMoat가치주", 0.25],
            ["381180", "TIGER 미국필라델피아반도체나스닥", 0.25]
        ],
        "balance": 1000000,
        "interval_month": 1,
        "start_date": "20100101",
        "end_date": "20221231"
    }
}
```

## 결과물

```
- Success Response:
    - Code: 200 Ok
    - Content:
    {
        "annual_return": 0.16,
        "mdd": -0.22789676206161769,
        "portfolio": {
            "KINDEX 미국WideMoat가치주": {
                "2010-10-31": 0.0,
                "2010-11-30": 0.0,
                ...
                "2022-10-31": 1.8642075395216862,
                "2022-11-30": 1.7864815565464127,
                "2022-12-31": 1.659809485204702
            },
            "TIGER 나스닥100": {
                "2010-10-31": 0.0,
                "2010-11-30": 0.0,
                "2022-10-31": 6.650569,
                "2022-11-30": 6.407668,
                "2022-12-31": 5.820596
                ...
                "2022-11-30": 0.9997847379184157,
                "2022-12-31": 0.8909697556775374
            },
            "backtest": {
                "2010-10-31": 0.99985,
                "2010-11-30": 1.038952,
                "2010-12-31": 1.058748,
            }
        },
        "sharpe_ratio": 0.79,
        "standard_deviation": 15.84,
        "total_balance": 5820596.307599997
    }

portfolio안에 종목별로 월별 수익률을 표기하여 출력.

연간 수익률,최대 낙폭률,sharpe ratio, 표준편차, 총 자산 등의 결과도 출

- Error Response:
    - Code: 404 Not found ( 해당 Stock code와 일치하는 stock이 없을 경우 )
    Content:
    {
        "error": "Stock code 381184 not found"
    }
    
    - Code: 400 Bad request ( 포트폴리오 종목 비율의 합이 1.0보다 클 경우 )
    Content:
{
    "error": "Sum of ratios is greater than 1.0"
}
