from numpy import int32

def data_to_analog_value(data: int) -> int:
    """
    Converts an internal analog state value to a [-65536, 65536] range.

    The function supports values outside the normal range, that is
    you can convert values in the extended range as well.

    Args:
        data (int): the internal value, usually stored in an event buffer
    
    Returns:
        int: the converted value
    """
    val = int32(data)
    val <<= int32(8)
    val >>= int32(8)
    return -val

def analog_value_to_data(value: int) -> int:
    """
    Converts a value in [-65536, 65536] range to an internal analog state value.

    The function supports values outside the normal range, that is
    you can convert values in the extended range as well.

    Args:
        data (int): the value to convert
    
    Returns:
        int: the converted value
    """
    value = -value
    value <<= int32(8)
    value >>= int32(8)
    return value