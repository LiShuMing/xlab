import pandas as pd
import pytest

def test_basic():
    events = pd.DataFrame({
        'event_time': ['2025-01-19 10:00:05', '2025-01-19 10:01:00', '2025-01-19 10:02:30'],
        'event': ['A', 'B', 'C']
    })
    events['event_time'] = pd.to_datetime(events['event_time'])
    print(events)

    prices = pd.DataFrame({
        'price_time': ['2025-01-19 10:00:00', '2025-01-19 10:01:15', '2025-01-19 10:02:00'],
        'price': [100, 105, 110]
    })
    prices['price_time'] = pd.to_datetime(prices['price_time'])
    print(prices)

    result = pd.merge_asof(events, prices, left_on='event_time', right_on='price_time')
    print(result)

def test_cow():
    # enable cow
    pd.options.mode.copy_on_write = True
    df = pd.DataFrame({"foo": [1, 2, 3], "bar": [4, 5, 6]})
    subset = df["foo"]
    subset.iloc[0] = 100
    print(subset)
    print(df)