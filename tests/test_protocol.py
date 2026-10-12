import pytest
from indoor_cycling.protocol import heart_rate_measurement, indoor_bike_data

def test_heart_rate_8bit():
    assert heart_rate_measurement(bytes([0,132])) == 132

def test_heart_rate_16bit():
    assert heart_rate_measurement(bytes([1,44,1])) == 300

def test_heart_rate_truncated():
    with pytest.raises(ValueError): heart_rate_measurement(bytes([1,2]))

def test_indoor_bike_power_cadence():
    # Speed omitted (bit 0 set); instantaneous cadence and power available.
    flags = (1 | (1 << 2) | (1 << 6)).to_bytes(2,"little")
    data = flags + (164).to_bytes(2,"little") + (92).to_bytes(2,"little",signed=True)
    assert indoor_bike_data(data) == {"cadence_rpm":82,"power_w":92}

def test_indoor_bike_truncated():
    with pytest.raises(ValueError): indoor_bike_data(bytes([0,0,1]))
