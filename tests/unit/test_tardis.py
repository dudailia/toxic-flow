from toxic_flow.data.tardis import dataset_url, incidents_on


def test_dataset_url_layout():
    assert dataset_url("2024-01-01", "trades") == (
        "https://datasets.tardis.dev/v1/binance-futures/trades/2024/01/01/BTCUSDT.csv.gz"
    )


def test_incident_inside_a_day_is_reported():
    inc = {"from": "2024-03-01T05:00:00.000Z", "to": "2024-03-01T05:10:00.000Z"}
    assert incidents_on(["2024-03-01", "2024-04-01"], [inc]) == {"2024-03-01": [inc]}


def test_incident_spanning_midnight_hits_both_days():
    inc = {"from": "2024-02-29T23:50:00.000Z", "to": "2024-03-01T00:10:00.000Z"}
    assert incidents_on(["2024-03-01"], [inc]) == {"2024-03-01": [inc]}


def test_incident_ending_at_midnight_does_not_hit_next_day():
    inc = {"from": "2024-02-29T23:50:00.000Z", "to": "2024-03-01T00:00:00.000Z"}
    assert incidents_on(["2024-03-01"], [inc]) == {}
