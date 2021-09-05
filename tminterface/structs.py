import struct
from enum import IntEnum
from tminterface.constants import MODE_RUN, SIM_HAS_TIMERS, SIM_HAS_DYNA, SIM_HAS_PLAYER_INFO
from tminterface.eventbuffer import Event


class CheckpointData(object):
    """
    The CheckpointData object represents checkpoint state within the game.

    The game keeps track of two arrays that contain checkpoint information.
    The first "state" array is an array of booleans (a boolean is 4 bytes long)
    and keeps track of which checkpoints were already passed. The length of the
    array represents the real count of the checkpoints on current the map (including finish).
    This does not mean that to finish the race the player has to pass through this exact count
    of checkpoints. A map with 3 laps and 5 checkpoints will still contain only 5 checkpoint states.

    The second "times" array is an array of structures with 2 fields: time and an unknown field.
    This array holds the "logical" number of checkpoints that have to be passed (including finish).
    This means the total number of checkpoint passes, including the existence of laps.

    Arguments:
        cp_states (list): the checkpoint states array
        cp_times (list): the checkpoint times array, each element is a two element tuple of (time, flags)
    """
    def __init__(self, cp_states: list, cp_times: list):
        self.cp_states = cp_states
        self.cp_times = cp_times


class SimStateData(object):
    """
    The SimStateData object represents a full save state of the simulation state,
    including checkpoint and input information.

    The simulation state consists of raw memory buffers representing various
    information about the race state. This includes the entirety of the vehicle
    state as well as the player info and other state variables such as current
    checkpoint count and input state.

    The memory regions themselves are monitored by TMInterface itself and are used
    for functionality like save states or fast rewind in the bruteforce script.
    TMInterface may use additional native game methods to restore the state based
    on information present in some of these memory regions. It is important to note
    that the buffers contain instance specific fields such as pointers and array sizes.
    These are masked out automatically by TMInterface when restoring the state
    (and when calling TMInterface.rewind_to_state).

    To query input state of the simulation state regardless of context,
    use input_* (input_accelerate, input_brake etc.) accessors.
    """
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
        self.input_running_event = Event(0)
        self.input_finish_event = Event(0)
        self.input_accelerate_event = Event(0)
        self.input_brake_event = Event(0)
        self.input_left_event = Event(0)
        self.input_right_event = Event(0)
        self.input_steer_event = Event(0)
        self.input_gas_event = Event(0)
        self.num_respawns = 0
        self.cp_data = None

    @property
    def time(self) -> int:
        if (self.flags & SIM_HAS_TIMERS) == 0:
            return 0

        return self.__get_int(self.timers, 4)

    @property
    def position(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]
        
        return self.__get_vec3(self.dyna, 500)

    @property
    def velocity(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]

        return self.__get_vec3(self.dyna, 512)

    # Available only in run context
    @property
    def display_speed(self) -> int:
        if (self.flags & SIM_HAS_PLAYER_INFO) == 0:
            return 0

        return self.__get_int(self.player_info, 832)

    @position.setter
    def position(self, pos: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.__set_vec3(self.dyna, 500, pos)
        return True

    @velocity.setter
    def velocity(self, vel: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.__set_vec3(self.dyna, 512, vel)
        return True

    @property
    def rotation_matrix(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [[0, 0, 0]] * 3

        m1 = self.__get_vec3(self.dyna, 464)
        m2 = self.__get_vec3(self.dyna, 476)
        m3 = self.__get_vec3(self.dyna, 488)

        return [m1, m2, m3]

    @rotation_matrix.setter
    def rotation_matrix(self, matrix: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.__set_vec3(self.dyna, 464, matrix[0])
        self.__set_vec3(self.dyna, 476, matrix[1])
        self.__set_vec3(self.dyna, 488, matrix[2])

    @property
    def race_time(self) -> int:
        if (self.flags & SIM_HAS_PLAYER_INFO) == 0:
            return False

        return self.__get_int(self.player_info, 688)

    @property
    def rewind_time(self) -> int:
        return self.race_time + 10

    @property
    def input_accelerate(self) -> bool:
        return self.input_accelerate_event.data if self.context_mode == MODE_RUN else self.input_accelerate_event.binary_value

    @property
    def input_brake(self) -> bool:
        return self.input_brake_event.data if self.context_mode == MODE_RUN else self.input_brake_event.binary_value

    @property
    def input_left(self) -> bool:
        return self.input_left_event.data if self.context_mode == MODE_RUN else self.input_left_event.binary_value

    @property
    def input_right(self) -> bool:
        return self.input_right_event.data if self.context_mode == MODE_RUN else self.input_right_event.binary_value

    @property
    def input_steer(self) -> int:
        return self.input_steer_event.data if self.context_mode == MODE_RUN else self.input_steer_event.analog_value

    @property
    def input_gas(self) -> int:
        return self.input_gas_event.data if self.context_mode == MODE_RUN else self.input_gas_event.analog_value

    @staticmethod
    def __get_int(buffer: bytearray, offset: int) -> int:
        return int.from_bytes(buffer[offset:offset+4], byteorder='little')

    @staticmethod
    def __get_vec3(buffer: bytearray, offset: int) -> list:
        x = struct.unpack('f', buffer[offset:offset+4])[0]
        y = struct.unpack('f', buffer[offset+4:offset+8])[0]
        z = struct.unpack('f', buffer[offset+8:offset+12])[0]
        return [x, y, z]

    @staticmethod
    def __set_vec3(buffer: bytearray, offset: int, v: list):
        buffer[offset:offset+4] = list(struct.pack('f', v[0]))
        buffer[offset+4:offset+8] = list(struct.pack('f', v[1]))
        buffer[offset+8:offset+12] = list(struct.pack('f', v[2]))


class BFPhase(IntEnum):
    INITIAL = 0
    SEARCH = 1


class BFTarget(IntEnum):
    FINISH_TIME = 0
    CHECKPOINT_TIME = 1
    TRIGGER = 2


class BFEvaluationDecision(IntEnum):
    CONTINUE = 0
    DO_NOTHING = 1
    ACCEPT = 2
    REJECT = 3
    STOP = 4


class BFEvaluationInfo(object):
    def __init__(self) -> None:
        self.phase = BFPhase.INITIAL
        self.target = BFTarget.FINISH_TIME
        self.time = 0
        self.modified_inputs_num = -1
        self.inputs_min_time = -1
        self.inputs_max_time = -1
        self.max_steer_diff = -1
        self.max_time_diff = -1
        self.override_stop_time = -1
        self.search_forever = False
        self.inputs_extend_steer = False


class BFEvaluationResponse(object):
    def __init__(self, decision: BFEvaluationDecision = BFEvaluationDecision.CONTINUE, rewind_time: int = -1) -> None:
        self.decision = decision
        self.rewind_time = rewind_time
