import struct
SIM_HAS_TIMERS = 0x1
SIM_HAS_STATE_1 = 0x2
SIM_HAS_STATE_2 = 0x4
SIM_HAS_STATE_3 = 0x8
SIM_HAS_STATE_4 = 0x10
SIM_HAS_CMD_BUFFER_CORE = 0x20
SIM_HAS_INPUT_STATE = 0x40

MODE_SIMULATION = 0
MODE_RUN = 1

class Event(object):
    def __init__(self, time: int, enabled: int, flags: int, name_index: int):
        self.time = time
        self.enabled = enabled
        self.flags = flags
        self.name_index = name_index

class EventBufferData(object):
    def __init__(self, events_duration: int):
        self.events_duration = events_duration
        self.events = []

    def copy(self):
        cpy = EventBufferData(self.events_duration)
        for ev in self.events:
            cpy.events.append(Event(ev.time, ev.enabled, ev.flags, ev.name_index))
        return cpy

    def clear(self):
        for i in range(1, len(self.events) - 1):
            self.events[i].time = 0xffffffff
            self.events[i].flags = 0
            self.events[i].enabled = 0
            self.events[i].name_index = 0xff

class CheckpointData(object):
    def __init__(self, cp_count: int, laps_count: int, cp_states: list, cp_times: list):
        self.cp_count = cp_count
        self.laps_count = laps_count
        self.cp_states = cp_states
        self.cp_times = cp_times

class SimStateData(object):
    def __init__(self):
        self.context_mode = MODE_RUN
        self.flags = 0
        self.timers = bytearray()
        self.state1 = bytearray()
        self.state2 = bytearray()
        self.state3 = bytearray()
        self.state4 = bytearray()
        self.cmd_buffer_core = bytearray()
        self.player_info = bytearray()
        self.input_running_state = 0
        self.input_finish_state  = 0
        self.input_accelerate_state = 0
        self.input_brake_state  = 0
        self.input_left_state  = 0
        self.input_right_state = 0
        self.input_steer_state = 0
        self.input_gas_state = 0
        self.num_respawns = 0
        self.cp_data = None

    def get_time(self) -> int:
        if (self.flags & SIM_HAS_TIMERS) == 0:
            return 0

        time = struct.unpack('i', self.timers[:4])[0]
        return time

    def get_position(self) -> list:
        if (self.flags & SIM_HAS_STATE_1) == 0:
            return [0, 0, 0]
        
        x = struct.unpack('f', self.state1[500:504])[0]
        y = struct.unpack('f', self.state1[504:508])[0]
        z = struct.unpack('f', self.state1[508:512])[0]
        return [x, y, z]

    def get_velocity(self) -> list:
        if (self.flags & SIM_HAS_STATE_1) == 0:
            return [0, 0, 0]
        
        x = struct.unpack('f', self.state1[512:516])[0]
        y = struct.unpack('f', self.state1[516:520])[0]
        z = struct.unpack('f', self.state1[520:524])[0]
        return [x, y, z]

    def get_aim_direction(self) -> list:
        if (self.flags & SIM_HAS_STATE_1) == 0:
            return [0, 0, 0]
        
        
        x = struct.unpack('f', self.state1[448:452])[0]
        y = struct.unpack('f', self.state1[452:456])[0]
        z = struct.unpack('f', self.state1[456:460])[0]
        return [x, y, z]

    def set_position(self, pos: list) -> bool:
        if (self.flags & SIM_HAS_STATE_1) == 0:
            return False

        self.state1[500:504] = list(struct.pack('f', pos[0]))
        self.state1[504:508] = list(struct.pack('f', pos[1]))
        self.state1[508:512] = list(struct.pack('f', pos[2]))
        return True

    def set_velocity(self, vel: list) -> bool:
        if (self.flags & SIM_HAS_STATE_1) == 0:
            return False

        self.state1[512:516] = list(struct.pack('f', vel[0]))
        self.state1[516:520] = list(struct.pack('f', vel[1]))
        self.state1[520:524] = list(struct.pack('f', vel[2]))
        return True

    def set_aim_direction(self, aim: list) -> bool:
        if (self.flags & SIM_HAS_STATE_1) == 0:
            return False

        self.state1[448:452] = list(struct.pack('f', aim[0]))
        self.state1[452:456] = list(struct.pack('f', aim[1]))
        self.state1[456:460] = list(struct.pack('f', aim[2]))
        return True
