import struct
import threading
import time
import mmap
import signal
import sys
from .client import Client
from .structs import Event, CheckpointData, SimStateData, EventBufferData
from .sizes import *

S_RESPONSE = 1
S_ON_RUN_STEP = 2
S_ON_SIM_BEGIN = 3
S_ON_SIM_STEP = 4
S_ON_SIM_END = 5
S_ON_CHECKPOINT_COUNT_CHANGED = 6
S_ON_LAPS_COUNT_CHANGED = 7
C_REGISTER = 8
C_DEREGISTER = 9
C_PROCESSED_CALL = 10
C_SET_INPUT_STATES = 11
C_RESPAWN = 12
C_SIM_REWIND_TO_STATE = 13
C_SIM_GET_STATE = 14
C_SIM_GET_EVENT_BUFFER = 15
C_SIM_GET_CONTROL_NAMES = 16
C_GET_CONTEXT_MODE = 17
C_SIM_SET_EVENT_BUFFER = 18
C_GET_CHECKPOINT_STATE = 19
C_SET_CHECKPOINT_STATE = 20
C_SET_GAME_SPEED = 21
C_EXECUTE_COMMAND = 22
C_SET_EXECUTE_COMMANDS = 23
C_SET_TIMEOUT = 24
ANY = 25

RESPONSE_TOO_LONG = 1
CLIENT_ALREADY_REGISTERED = 2
NO_EVENT_BUFFER = 3
INVALID_EVENT_BUFFER_SIZE = 4
NO_CHECKPOINT_STATE = 5

MAXINT32 = 2 ** 31 - 1

class Message(object):
    def __init__(self, _type: int, error_code=0):
        self._type = _type
        self.error_code = error_code
        self.data = bytearray()

    def write_event(self, event: Event):
        self.write_uint32(event.time)
        self.write_int32(event.data)

    def write_uint8(self, n):
        self.data.extend(struct.pack('B', n))

    def write_int16(self, n: int):
        self.data.extend(struct.pack('h', n))

    def write_uint16(self, n: int):
        self.data.extend(struct.pack('H', n))

    def write_int32(self, n: int):
        self.data.extend(struct.pack('i', n))

    def write_uint32(self, n: int):
        self.data.extend(struct.pack('I', n))

    def write_double(self, n: float):
        self.data.extend(struct.pack('d', n))

    def write_buffer(self, buffer: bytearray):
        self.data.extend(buffer)

    def write_zeros(self, n_bytes):
        self.data.extend(bytearray(n_bytes))

    def write_int(self, n, size):
        if size  == 1:
            self.write_uint8(n)
        elif size == 2:
            if n < 0:
                self.write_int16(n)
            else:
                self.write_uint16(n)
        elif size == 4:
            if n == 0xffffffff:
                self.write_uint32(n)
            else:
                self.write_int32(n)

    def to_data(self) -> bytearray:
        return bytearray(struct.pack('i', self._type)) + bytearray(struct.pack('i', self.error_code)) + self.data

    def __len__(self):
        return 8 + len(self.data)


class TMInterface(object):
    ''' 
    TMInterface is the main class to communicate with the TMInterface server.
    The communication is done through memory mapping and a simple synchronous
    message system between the server and the client. A TMInterface server
    can only serve only one client at a time, it is however possible to connect
    to many servers from the same script.

    The interface provides various functions to manipulate game state
    and hook to different periods of game execution. 

    Args:
        server_name (str): the server tag to connect to
        buffer_size (int): the buffer size used by the server, by default it's 16834

    Attributes:
        server_name (str): the server tag that's used
        running (bool): whether the client is running or not
        registered (bool): whether the client is registered
        mfile (mmap.mmap): the internal mapped file used for communication
        buffer_size (int): the buffer size used for communication
        client (Client): the registered client that's controlling the server
    '''
    def __init__(self, server_name='TMInterface0', buffer_size=16384):
        self.server_name = server_name
        self.running = True
        self.registered = False
        self.mfile = None
        self.buffer_size = buffer_size
        self.client = None
        self.empty_buffer = bytearray(self.buffer_size)
        self.thread = None

    def register(self, client: Client):
        if self.client is not None:
            return

        self.registered = False
        self.client = client

        if self.thread is None:
            self.thread = threading.Thread(target=self.__main_thread)
            self.thread.daemon = True
            self.thread.start()

    def close(self):
        self.running = False

        if self.registered:
            msg = Message(C_DEREGISTER)
            self.__send_message(msg)
            self.__wait_for_server_response()
            self.client.on_deregistered(self)

            if self.thread is not None:
                self.thread = None

    def set_timeout(self, timeout: int):
        msg = Message(C_SET_TIMEOUT)
        msg.write_int32(timeout)
        self.__send_message(msg)
        self.__wait_for_server_response()

    def set_speed(self, speed: float):
        msg = Message(C_SET_GAME_SPEED)
        msg.write_double(speed)
        self.__send_message(msg)
        self.__wait_for_server_response()

    def set_input_state(self, left=-1, right=-1, up=-1, down=-1, steer=MAXINT32, gas=MAXINT32):
        msg = Message(C_SET_INPUT_STATES)
        msg.write_int32(left)
        msg.write_int32(right)
        msg.write_int32(up)
        msg.write_int32(down)
        msg.write_int32(steer)
        msg.write_int32(gas)
        self.__send_message(msg)
        self.__wait_for_server_response()

    def execute_command(self, command: str):
        msg = Message(C_EXECUTE_COMMAND)
        msg.write_int32(0)
        self.__write_vector(msg, [ord(c) for c in command], 1)
        self.__send_message(msg)
        self.__wait_for_server_response()

    def rewind_to_state(self, state: SimStateData):
        msg = Message(C_SIM_REWIND_TO_STATE)
        msg.write_int32(state.context_mode)
        msg.write_int32(state.flags)
        msg.write_buffer(state.timers)
        msg.write_buffer(state.dyna)
        msg.write_buffer(state.scene_mobil)
        msg.write_buffer(state.simulation_wheels)
        msg.write_buffer(state.plug_solid)
        msg.write_buffer(state.cmd_buffer_core)
        msg.write_buffer(state.player_info)
        msg.write_buffer(state.internal_input_state)

        msg.write_event(state.input_running_state)
        msg.write_event(state.input_finish_state)
        msg.write_event(state.input_accelerate_state)
        msg.write_event(state.input_brake_state)
        msg.write_event(state.input_left_state)
        msg.write_event(state.input_right_state)
        msg.write_event(state.input_steer_state)
        msg.write_event(state.input_gas_state)
        msg.write_uint32(state.num_respawns)

        self.__write_checkpoint_state(msg, state.cp_data)
        self.__send_message(msg)
        self.__wait_for_server_response()

    def set_checkpoint_state(self, data: CheckpointData):
        msg = Message(C_SET_CHECKPOINT_STATE)
        self.__write_checkpoint_state(msg, data)
        self.__send_message(msg)
        self.__wait_for_server_response()

    def set_event_buffer(self, data: EventBufferData):
        msg = Message(C_SIM_SET_EVENT_BUFFER)
        msg.write_int32(data.events_duration)
        events_tup = [(event.time, event.data) for event in data.events]

        self.__write_vector(msg, events_tup, [4, 4])
        self.__send_message(msg)
        self.__wait_for_server_response()

    def __write_checkpoint_state(self, msg: Message, data):
        msg.write_int32(data.cp_count)
        msg.write_int32(data.laps_count)
        self.__write_vector(msg, data.cp_states, 4)
        self.__write_vector(msg, data.cp_times, [4, 4])

    def __read_checkpoint_state(self):
        cp_count = self.__read_int32()
        laps_count = self.__read_int32()
        cp_states = self.__read_vector(4)
        cp_times = self.__read_vector([4, 4])

        data = CheckpointData(cp_count, laps_count, cp_states, cp_times)
        return data

    def get_context_mode(self) -> int:
        msg = Message(C_GET_CONTEXT_MODE)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(8)
        return self.__read_int32()

    def get_checkpoint_state(self) -> CheckpointData:
        msg = Message(C_GET_CHECKPOINT_STATE)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self.__read_int32()
        if (error_code & NO_CHECKPOINT_STATE) == 0:
            data = self.__read_checkpoint_state()
        else:
            data = None

        self.__clear_buffer()
        return data

    def __read_event(self):
        time = self.__read_uint32()
        data = self.__read_int32()
        return Event(time, data)

    def get_simulation_state(self) -> SimStateData:
        msg = Message(C_SIM_GET_STATE)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self.__read_int32()

        state = SimStateData()
        state.context_mode = self.__read_int32()
        state.flags = self.__read_uint32()
        state.timers = bytearray(self.mfile.read(TIMERS_SIZE))
        state.dyna = bytearray(self.mfile.read(DYNA_SIZE))
        state.scene_mobil = bytearray(self.mfile.read(SCENE_MOBIL_SIZE))
        state.simulation_wheels = bytearray(self.mfile.read(SIMULATION_WHEELS_SIZE))
        state.plug_solid = bytearray(self.mfile.read(PLUG_SOLID_SIZE))
        state.cmd_buffer_core = bytearray(self.mfile.read(CMD_BUFFER_CORE_SIZE))
        state.player_info = bytearray(self.mfile.read(PLAYER_INFO_SIZE))
        state.internal_input_state = bytearray(self.mfile.read(INPUT_STATE_SIZE))

        state.input_running_state = self.__read_event()
        state.input_finish_state  = self.__read_event()
        state.input_accelerate_state = self.__read_event()
        state.input_brake_state  = self.__read_event()
        state.input_left_state  = self.__read_event()
        state.input_right_state = self.__read_event()
        state.input_steer_state = self.__read_event()
        state.input_gas_state = self.__read_event()
        state.num_respawns = self.__read_uint32()

        if (error_code & NO_CHECKPOINT_STATE) == 0:
            state.cp_data = self.__read_checkpoint_state()
        else:
            state.cp_data = CheckpointData(0, 0, [], [])

        self.__clear_buffer()
        return state

    def get_event_buffer(self) -> EventBufferData:
        msg = Message(C_SIM_GET_EVENT_BUFFER)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        self.mfile.seek(4)
        error_code = self.__read_uint32()
        if error_code == NO_EVENT_BUFFER:
            return EventBufferData(0)

        data = EventBufferData(self.__read_uint32())
        event_data = self.__read_vector([4, 4])
        for item in event_data:
            ev = Event(item[0], item[1])
            data.events.append(ev)
            
        self.__clear_buffer()
        return data

    def get_control_names(self) -> dict:
        msg = Message(C_SIM_GET_CONTROL_NAMES)
        self.__send_message(msg)
        self.__wait_for_server_response(False)

        names = {}
        self.mfile.seek(8)
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = '_FakeIsRaceRunning'
        
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = '_FakeFinishLine'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Accelerate'
            
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Brake'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'SteerLeft'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'SteerRight'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Steer'
            
        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Gas'

        _id = self.__read_int32()
        if _id != -1:
            names[_id] = 'Respawn'

        self.__clear_buffer()
        return names

    def __write_vector(self, msg: Message, vector: list, field_sizes):
        if len(msg) + 4 > self.buffer_size:
            msg.error_code = RESPONSE_TOO_LONG
            return
        
        vsize = len(vector)
        msg.write_int32(vsize)
        if vsize == 0:
            return

        is_list = isinstance(field_sizes, list)
        if is_list:
            item_size = sum(field_sizes)
        else:
            item_size = field_sizes

        msgsize = len(msg) + item_size * vsize
        if msgsize > self.buffer_size:
            msg.data = msg.data[:-4]
            msg.write_int32(0)
            msg.error_code = RESPONSE_TOO_LONG
            return

        if is_list:
            for elem in vector:
                for i, field in enumerate(elem):
                    msg.write_int(field, field_sizes[i])
        else:
            for elem in vector:
                msg.write_int(elem, field_sizes)


    def __read_vector(self, field_sizes) -> list:
        if self.mfile.tell() + 4 > self.buffer_size:
            return []

        size = self.__read_int32()
        vec = []
        for _ in range(size):
            if isinstance(field_sizes, list):
                tup = []
                for size in field_sizes:
                    tup.append(self.__read_int(size))

                vec.append(tuple(tup))
            else:
                vec.append(self.__read_int(field_sizes))
        
        return vec

    def __main_thread(self):
        while self.running:
            if not self.__ensure_connected():
                time.sleep(0)
                continue

            if not self.registered:
                msg = Message(C_REGISTER)
                self.__send_message(msg)
                self.__wait_for_server_response()
                self.client.on_registered(self)
                self.registered = True

            self.process_server_message()
            time.sleep(0)

    def process_server_message(self):
        if self.mfile is None:
            return
        
        self.mfile.seek(0)
        msgtype = self.__read_int32()
        if msgtype & 0xFF00 == 0:
            return

        msgtype &= 0xFF

        # error_code = self.__read_int32()
        self.__skip(4)

        if msgtype == S_ON_RUN_STEP:
            time = self.__read_int32()
            self.client.on_run_step(self, time)
            self.__respond_to_call(msgtype)
        elif msgtype == S_ON_SIM_BEGIN:
            self.client.on_simulation_begin(self)
            self.__respond_to_call(msgtype)
        elif msgtype == S_ON_SIM_STEP:
            time = self.__read_int32()
            self.client.on_simulation_step(self, time)
            self.__respond_to_call(msgtype)
        elif msgtype == S_ON_SIM_END:
            result = self.__read_int32()
            self.client.on_simulation_end(self, result)
            self.__respond_to_call(msgtype)   
        elif msgtype == S_ON_CHECKPOINT_COUNT_CHANGED:
            current  = self.__read_int32()
            target = self.__read_int32()
            self.client.on_checkpoint_count_changed(self, current, target)
            self.__respond_to_call(msgtype)
        elif msgtype == S_ON_LAPS_COUNT_CHANGED:
            current = self.__read_int32()
            self.client.on_laps_count_changed(self, current)
            self.__respond_to_call(msgtype)

    def __ensure_connected(self):
        if self.mfile is not None:
            return True
            
        try:
            self.mfile = mmap.mmap(-1, self.buffer_size, tagname=self.server_name)
            return True
        except Exception as e:
            print(e)

        return False

    def __wait_for_server_response(self, clear=True):
        if self.mfile is None:
            return

        self.mfile.seek(0)
        while self.__read_int32() != S_RESPONSE | 0xFF00:
            self.mfile.seek(0)
            time.sleep(0)

        # self.mfile.seek(4)
        # error_code = self.__read_int32()
        # if error_code != 0:
        #     print('Got error code:', error_code)
        
        # self.mfile.seek(0)

        if clear:
            self.__clear_buffer()

    def __respond_to_call(self, msgtype):
        msg = Message(C_PROCESSED_CALL)
        msg.write_int32(msgtype)
        self.__send_message(msg)

    def __send_message(self, message):
        if self.mfile is None:
            return
        
        data = message.to_data()
        self.mfile.seek(0)
        self.mfile.write(data)

        self.mfile.seek(1)
        self.mfile.write(bytearray([0xFF]))

    def __clear_buffer(self):
        self.mfile.seek(0)
        self.mfile.write(self.empty_buffer)

    def __read(self, num_bytes, typestr):
        try:
            return struct.unpack(typestr, self.mfile.read(num_bytes))[0]
        except Exception as e:
            print(e)
            return 0

    def __read_int(self, size):
        if size == 1:
            return self.__read_uint8()
        if size == 2:
            return self.__read_uint16()
        elif size == 4:
            return self.__read_int32()
        
        return 0

    def __read_uint8(self):
        return self.__read(1, 'B')

    def __read_int32(self):
        return self.__read(4, 'i')
    
    def __read_uint32(self):
        return self.__read(4, 'I')

    def __read_uint16(self):
        return self.__read(2, 'H')

    def __skip(self, n):
        self.mfile.seek(self.mfile.tell() + n)
