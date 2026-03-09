import time

import psycopg2
import json
import finnhub
# JSON đầu vào
finnhub_client = finnhub.Client(api_key="d3d027pr01qmnfgfhi7gd3d027pr01qmnfgfhi80")

conn = psycopg2.connect(
    host="localhost",
    dbname="stock_management",
    user="postgres",
    password="postgres"
)
cur = conn.cursor()

def get_data(ticker):
    return finnhub_client.company_profile2(symbol=ticker)


# data = {
#     "country": "US",
#     "currency": "USD",
#     "exchange": "NASDAQ/NMS (GLOBAL MARKET)",
#     "ipo": "1980-12-12",
#     "marketCapitalization": 1415993,
#     "name": "Apple Inc",
#     "phone": "14089961010",
#     "shareOutstanding": 4375.47998046875,
#     "ticker": "AAPL",
#     "weburl": "https://www.apple.com/",
#     "logo": "https://static.finnhub.io/logo/87cb30d8-80df-11ea-8951-00000000092a.png",
#     "finnhubIndustry": "Technology"
# }

# Map key JSON → tên cột trong bảng
def insert_company_profile(ticker):
    data = get_data(ticker)
    column_map = {
        "ticker": "ticker",
        "name": "name",
        "country": "country",
        "currency": "currency",
        "exchange": "exchange",
        "ipo": "ipo",
        "marketCapitalization": "market_capitalization",
        "shareOutstanding": "share_outstanding",
        "phone": "phone",
        "weburl": "weburl",
        "logo": "logo",
        "finnhubIndustry": "finnhub_industry"
    }

    # Lấy danh sách cột và giá trị theo đúng thứ tự
    columns = []
    values = []
    for key_json, col in column_map.items():
        columns.append(col)
        values.append(data.get(key_json))

    # Tạo placeholder %s
    placeholders = ",".join(["%s"] * len(values))

    sql = f"""
        INSERT INTO company_profile ({",".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (ticker) DO NOTHING;
    """

    # Thực thi
    cur.execute(sql, values)

def main():
    with open("list_symbol.txt", "r") as f:
        for line in f:
            ticker = line.strip()
            insert_company_profile(ticker)
            print(f"Inserted/Skipped: {ticker}")
            time.sleep(1)
    conn.commit()

if __name__ == "__main__":
    main()
    cur.close()
    conn.close()

