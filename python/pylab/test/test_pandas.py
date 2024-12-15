import pandas as pd
import pytest

def test_pandas():
    events = pd.DataFrame({
        'event_time': ['10:00:05', '10:01:00', '10:02:30'],
        'event': ['A', 'B', 'C']
    })
    events['event_time'] = pd.to_datetime(events['event_time'])

    prices = pd.DataFrame({
        'price_time': ['10:00:00', '10:01:15', '10:02:00'],
        'price': [100, 105, 110]
    })
    prices['price_time'] = pd.to_datetime(prices['price_time'])
    print(events)
    print(prices)

    result = pd.merge_asof(events, prices, left_on='event_time', right_on='price_time')
    print(result)