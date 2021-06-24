import tminterface.util as util
import struct

SIM_HAS_TIMERS = 0x1
SIM_HAS_DYNA = 0x2
SIM_HAS_SCENE_MOBIL = 0x4
SIM_HAS_SIMULATION_WHEELS = 0x8
SIM_HAS_PLUG_SOLID = 0x10
SIM_HAS_CMD_BUFFER_CORE = 0x20
SIM_HAS_INPUT_STATE = 0x40
SIM_HAS_PLAYER_INFO = 0x80

MODE_SIMULATION = 0
MODE_RUN = 1

class Event(object):
    def __init__(self, time: int, data: int):
        self.time = time
        self.data = data

    @property
    def name_index(self) -> int:
        return self.data >> 24

    @name_index.setter
    def name_index(self, index: int):
        self.data &= 0xFFFFFF
        self.data |= (index << 24)

    @property
    def binary_value(self) -> int:
        return self.data & 0xFFFFFF

    @binary_value.setter
    def binary_value(self, value: int) -> int:
        self.data = self.data & 0xFF000000 | value

    @property
    def analog_value(self) -> int:
        return util.data_to_analog_value(self.data & 0xFFFFFF)

    @analog_value.setter
    def analog_value(self, value: int):
        self.data = self.data & 0xFF000000 | (util.analog_value_to_data(value) & 0xFFFFFF)


class EventBufferData(object):
    def __init__(self, events_duration: int):
        self.events_duration = events_duration
        self.control_names = {}
        self.events = []

    def copy(self):
        cpy = EventBufferData(self.events_duration)
        for ev in self.events:
            cpy.events.append(Event(ev.time, ev.data))
        return cpy

    def clear(self):
        self.events = []

    def sort(self):
        self.events = sorted(self.events, key=lambda ev: ev.time, reverse=True)

class CheckpointData(object):
    def __init__(self, cp_states: list, cp_times: list):
        self.cp_states = cp_states
        self.cp_times = cp_times

class SimStateData(object):
    def __init__(self):
        self.version = 0
        self.context_mode = MODE_RUN
        self.flags = 0
        self.timers = bytearray()
        self.dyna = bytearray()
        self.scene_mobil = bytearray()
        self.simulation_wheels = bytearray()
        self.plug_solid = bytearray()
        self.cmd_buffer_core = bytearray()
        self.player_info = bytearray()
        self.internal_input_state = bytearray()
        self.input_running_state = Event(0, 0)
        self.input_finish_state = Event(0, 0)
        self.input_accelerate_state = Event(0, 0)
        self.input_brake_state  = Event(0, 0)
        self.input_left_state = Event(0, 0)
        self.input_right_state = Event(0, 0)
        self.input_steer_state = Event(0, 0)
        self.input_gas_state = Event(0, 0)
        self.num_respawns = 0
        self.cp_data = None

    def get_time(self) -> int:
        if (self.flags & SIM_HAS_TIMERS) == 0:
            return 0

        return self.__get_int(self.timers, 4)

    def get_position(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]
        
        x = struct.unpack('f', self.dyna[500:504])[0]
        y = struct.unpack('f', self.dyna[504:508])[0]
        z = struct.unpack('f', self.dyna[508:512])[0]
        return [x, y, z]

    def get_velocity(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]
        
        x = struct.unpack('f', self.dyna[512:516])[0]
        y = struct.unpack('f', self.dyna[516:520])[0]
        z = struct.unpack('f', self.dyna[520:524])[0]
        return [x, y, z]

    def get_aim_direction(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]
        
        x = struct.unpack('f', self.dyna[448:452])[0]
        y = struct.unpack('f', self.dyna[452:456])[0]
        z = struct.unpack('f', self.dyna[456:460])[0]
        return [x, y, z]

    def get_display_speed(self) -> int:
        if (self.flags & SIM_HAS_PLAYER_INFO) == 0:
            return 0

        return struct.unpack('i', self.player_info[832:836])[0]

    def set_position(self, pos: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.dyna[500:504] = list(struct.pack('f', pos[0]))
        self.dyna[504:508] = list(struct.pack('f', pos[1]))
        self.dyna[508:512] = list(struct.pack('f', pos[2]))
        return True

    def set_velocity(self, vel: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.dyna[512:516] = list(struct.pack('f', vel[0]))
        self.dyna[516:520] = list(struct.pack('f', vel[1]))
        self.dyna[520:524] = list(struct.pack('f', vel[2]))
        return True

    def set_aim_direction(self, aim: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.dyna[448:452] = list(struct.pack('f', aim[0]))
        self.dyna[452:456] = list(struct.pack('f', aim[1]))
        self.dyna[456:460] = list(struct.pack('f', aim[2]))
        return True

    @staticmethod
    def __get_int(buffer, offset: int) -> int:
        return int.from_bytes(buffer[offset:offset+4], byteorder='little')
