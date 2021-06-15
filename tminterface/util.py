from numpy import int32

def data_to_analog_value(data: int) -> int:
    val = int32(data)
    val <<= int32(8)
    val >>= int32(8)
    return -val

def analog_value_to_data(value: int) -> int:
    value = -value
    value <<= int32(8)
    value >>= int32(8)
    return value