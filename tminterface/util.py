from numpy import int32
import numpy as np
import math

EPSILON = 0.00001

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


def quat_to_ypw(quat: np.array) -> np.array:
    """
    Converts a quaternion to yaw, pitch and roll values.

    This function uses the internal implementation that the game
    uses to convert quaternions to yaw, pitch and roll.

    The function itself is constructed from reverse engineering
    the code of the game. Note that this particular implementation
    is not 100% compatible with the actual assembly code, however it
    should produce the same results in most cases.

    Args:
        quat (np.array): the quaternion to convert (x, y, z, w)

    Returns:
        np.array: an array containing 3 elements: yaw, pitch and roll
    """
    t0 = quat[2] * quat[1] + quat[3] * quat[0]

    if abs(t0 + 0.5) < EPSILON or t0 + 0.5 <= 0:
        yaw = math.atan2(quat[1], quat[0])
        return np.array([yaw * 2, -1.57079637, 0])

    if abs(t0 - 0.5) < EPSILON or t0 - 0.5 >= 0:
        yaw = math.atan2(quat[1], quat[0])
        return np.array([-yaw * 2, 1.57079637, 0])

    yaw = math.atan2(2.0 * (quat[2] * quat[0] - quat[3] * quat[1]), 1.0 - (quat[3] * quat[3] + quat[2] * quat[2]) * 2.0)
    roll = math.asin(2.0 * t0)
    pitch = math.atan2(2.0 * (quat[0] * quat[1] - quat[2] * quat[3]), 1.0 - 2.0 * (quat[1] * quat[1] + quat[3] * quat[3]))
    return np.array([yaw, pitch, roll])


def mat3_to_quat(mat: np.array) -> np.array:
    """
    Converts a rotation matrix to a quaternion.

    This function uses the internal implementation that the game
    uses to convert a rotation matrix to a quaternion.

    The function itself is constructed from reverse engineering
    the code of the game. This particular implementation should be
    100% compatible with the original method the game uses.
    Note however that this compatibility is not guaranteed.

    Args:
        mat (np.array): a 3x3 rotation matrix to convert

    Returns:
        np.array: the quaternion consisting of 4 elements (x, y, z, w)
    """
    trace = np.trace(mat)

    if trace > 0:
        trace += 1
        trace_squared = math.sqrt(trace)

        trace  = 0.5 / trace_squared
        return np.array([
            trace_squared / 2,
            trace * (mat[2, 1] - mat[1, 2]),
            trace * (mat[0, 2]  - mat[2, 0]),
            trace * (mat[1, 0] - mat[0, 1])
        ])

    index = 0
    if mat[1, 1] > mat[0, 0]:
        index = 1
    elif mat[2, 2] > mat[0, 0]:
        index = 2

    indexes = [1, 2, 0]
    var_1 = indexes[index]
    var_2 = indexes[var_1]

    trace = mat[index, index] - (mat[var_2, var_2] + mat[var_1, var_1]) + 1.0

    trace_squared = math.sqrt(trace)
    trace = 0.5 / trace_squared

    quat = np.zeros(4)
    quat[0] = trace * (mat[var_2, var_1] - mat[var_1, var_2])
    quat[index + 1] = trace_squared / 2
    quat[var_1 + 1] = trace * (mat[index, var_1] + mat[var_1, index])
    quat[var_2 + 1] = trace * (mat[index, var_2] + mat[var_2, index])
    return quat
