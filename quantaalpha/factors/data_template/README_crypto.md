# How to read files.
For example, if you want to read `filename.h5`
```Python
import pandas as pd
df = pd.read_pickle("filename.h5", key="data")
```
NOTE: **key is always "data" for all hdf5 files **.

# Here is a short description about the data

| Filename       | Description                                                      |
| -------------- | -----------------------------------------------------------------|
| "daily_pv.h5"  | Daily price and volume data for top-50 cryptocurrencies (2020-2025). |


# For different data, We have some basic knowledge for them

## Daily data variables
$open: open price of the cryptocurrency on that day.
$close: close price of the cryptocurrency on that day.
$high: high price of the cryptocurrency on that day.
$low: low price of the cryptocurrency on that day.
$volume: trading volume (base currency) of the cryptocurrency on that day.
$return: daily return of the cryptocurrency on that day.
$factor: adjustment factor (always 1.0 for crypto, no corporate actions).

## Market characteristics
- **24/7 trading**: Crypto markets never close. Every calendar day has a data point.
- **Cross-sectional pool**: ~50 coins (BTC, ETH, SOL, etc.) form the universe each day.
- **High volatility**: Daily returns of ±10-20% are not uncommon.
- **No price limits**: No circuit breakers or up/down limits.
- **All prices in USDT**: Stablecoin-quoted, no dividend/split adjustments needed.
