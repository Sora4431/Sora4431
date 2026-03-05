import pandas as pd
import re

df = pd.read_csv('market-data/market_data.csv')

if 'market_open' in df.columns:
    latest = df[df['market_open'] == 1].iloc[-1]
else:
    latest = df.iloc[-1]

date = latest['date']

sp500       = f"${latest['sp500']:,.2f}"
sp500_ch    = latest['sp500_change']
sp500_pct   = latest['sp500_pct']
sp500_arrow = "📈" if sp500_ch >= 0 else "📉"

wti         = f"${latest['wti']:,.2f}/bbl"
wti_ch      = latest['wti_change']
wti_pct     = latest['wti_pct']
wti_arrow   = "📈" if wti_ch >= 0 else "📉"

us10y       = f"{latest['us10y']:.4f}%"
us10y_ch    = latest['us10y_change']
us10y_pct   = latest['us10y_pct']
us10y_arrow = "📈" if us10y_ch >= 0 else "📉"

chart_sp500_url = "https://raw.githubusercontent.com/Sora4431/market-data/main/chart_sp500.svg"
chart_wti_url   = "https://raw.githubusercontent.com/Sora4431/market-data/main/chart_wti.svg"
chart_us10y_url = "https://raw.githubusercontent.com/Sora4431/market-data/main/chart_us10y.svg"

new_section = f"""<!--START_MARKET_DATA-->
| Market | Price | Change | Date |
|--------|-------|--------|------|
| 🇺🇸 **S&P 500** | {sp500} | {sp500_arrow} {sp500_ch:+.2f} ({sp500_pct:+.2f}%) | {date} |
| 🛢️ **WTI Crude** | {wti} | {wti_arrow} {wti_ch:+.2f} ({wti_pct:+.2f}%) | {date} |
| 🏦 **US 10Y Yield** | {us10y} | {us10y_arrow} {us10y_ch:+.4f} ({us10y_pct:+.2f}%) | {date} |


<p align="center">
  <img src="{chart_sp500_url}" alt="S&P 500" width="30%" />
  <img src="{chart_wti_url}" alt="WTI Crude Oil" width="30%" />
  <img src="{chart_us10y_url}" alt="US 10-Year Treasury Yield" width="30%" />
</p>

<!--END_MARKET_DATA-->"""

with open('README.md', 'r') as f:
    content = f.read()

pattern = r'<!--START_MARKET_DATA-->.*?<!--END_MARKET_DATA-->'
content = re.sub(pattern, new_section, content, flags=re.DOTALL)

with open('README.md', 'w') as f:
    f.write(content)

print(f"Updated market data for {date}")
