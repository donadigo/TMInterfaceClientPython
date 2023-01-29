from bytefield import (
    ByteStruct,
    FloatField,
    IntegerField,
    ArrayField,
    BooleanField,
    ByteArrayField,
    StructField,
    StringField
)
from enum import IntEnum
from tminterface.constants import  SIM_HAS_TIMERS, SIM_HAS_DYNA, SIM_HAS_PLAYER_INFO
from tminterface.eventbuffer import Event
import tminterface.util as util
import numpy as np


class PlayerInfoStruct(ByteStruct):
    """
    Attributes:
        team: int
        prev_race_time: int
        race_time: int
        race_time : int
        race_best_time : int
        lap_start_time : int
        lap_time : int
        lap_best_time : int
        min_respawns : int
        nb_completed : int
        max_completed : int
        stunts_score : int
        best_stunts_score : int
        cur_checkpoint : int
        average_rank : float
        current_race_rank : int
        current_round_rank : int
        current_time : int
        race_state : int
        ready_enum : int
        round_num : int
        offset_current_cp : float
        cur_lap_cp_count : int
        cur_cp_count : int
        cur_lap : int
        race_finished : bool
        display_speed : int
        finish_not_passed : bool
        countdown_time : int
        rest : bytearray
    """

    team                = IntegerField(offset=576, signed=False)
    prev_race_time      = IntegerField(offset=680)
    race_start_time     = IntegerField(signed=False)
    race_time           = IntegerField(signed=True)
    race_best_time      = IntegerField(signed=False)
    lap_start_time      = IntegerField(signed=False)
    lap_time            = IntegerField(signed=False)
    lap_best_time       = IntegerField()
    min_respawns        = IntegerField(signed=False)
    nb_completed        = IntegerField(signed=False)
    max_completed       = IntegerField(signed=False)
    stunts_score        = IntegerField(signed=False)
    best_stunts_score   = IntegerField(signed=False)
    cur_checkpoint      = IntegerField(signed=False)
    average_rank        = FloatField()
    current_race_rank   = IntegerField(signed=False)
    current_round_rank  = IntegerField(signed=False)
    current_time        = IntegerField(offset=776, signed=False)
    race_state          = IntegerField(offset=788, signed=False)
    ready_enum          = IntegerField(signed=False)
    round_num           = IntegerField(signed=False)
    offset_current_cp   = FloatField()
    cur_lap_cp_count    = IntegerField(offset=816, signed=False)
    cur_cp_count        = IntegerField(signed=False)
    cur_lap             = IntegerField(signed=False)
    race_finished       = BooleanField()
    display_speed       = IntegerField()
    finish_not_passed   = BooleanField()
    countdown_time      = IntegerField(offset=916)
    rest                = ByteArrayField(32)


class HmsDynaStateStruct(ByteStruct):
    """
    Attributes:
        quat: np.ndarray
        rotation: np.ndarray
        position: np.ndarray
        linear_speed: np.ndarray
        add_linear_speed: np.ndarray
        angular_speed: np.ndarray
        force: np.ndarray
        torque: np.ndarray
        inverse_inertia_tensor: np.ndarray
        unknown: float
        not_tweaked_linear_speed: np.ndarray
        owner: int
    """

    quat                        = ArrayField(offset=0, shape=(4,), elem_field_type=FloatField)
    rotation                    = ArrayField(shape=(3, 3), elem_field_type=FloatField)
    position                    = ArrayField(shape=(3,), elem_field_type=FloatField)
    linear_speed                = ArrayField(shape=(3,), elem_field_type=FloatField)
    add_linear_speed            = ArrayField(shape=(3,), elem_field_type=FloatField)
    angular_speed               = ArrayField(shape=(3,), elem_field_type=FloatField)
    force                       = ArrayField(shape=(3,), elem_field_type=FloatField)
    torque                      = ArrayField(shape=(3,), elem_field_type=FloatField)
    inverse_inertia_tensor      = ArrayField(shape=(3, 3), elem_field_type=FloatField)
    unknown                     = FloatField()
    not_tweaked_linear_speed    = ArrayField(shape=(3,), elem_field_type=FloatField)
    owner                       = IntegerField()

    @property
    def inverse_intertia_tensor(self):
        return self.inverse_inertia_tensor

    @inverse_intertia_tensor.setter
    def inverse_intertia_tensor(self, tensor):
        self.inverse_inertia_tensor = tensor


class HmsDynaStruct(ByteStruct):
    """
    Attributes:
        previous_state: HmsDynaStateStruct
        current_state: HmsDynaStateStruct
        temp_state: HmsDynaStateStruct
        rest: bytearray
    """

    previous_state  = StructField(offset=268, struct_type=HmsDynaStateStruct, instance_with_parent=False)
    current_state   = StructField(struct_type=HmsDynaStateStruct, instance_with_parent=False)
    temp_state      = StructField(struct_type=HmsDynaStateStruct, instance_with_parent=False)
    rest            = ByteArrayField(616)

    @property
    def prev_state(self):
        return self.temp_state

    @prev_state.setter
    def prev_state(self, state):
        self.temp_state = state


class SurfaceHandler(ByteStruct):
    """
    Attributes:
        unknown: np.ndarray
        rotation: np.ndarray
        position: np.ndarray
    """

    unknown     = ArrayField(offset=4, shape=(4, 3), elem_field_type=FloatField)
    rotation    = ArrayField(shape=(3, 3), elem_field_type=FloatField)
    position    = ArrayField(shape=3, elem_field_type=FloatField)


class RealTimeState(ByteStruct):
    """
    Attributes:
        damper_absorb: float
        field_4: float
        field_8: float
        field_12: np.ndarray
        field_48: np.ndarray
        field_84: np.ndarray
        field_108: float
        has_ground_contact: bool
        contact_material_id: int
        is_sliding: bool
        relative_rotz_axis: np.ndarray
        nb_ground_contacts: int
        field_144: np.ndarray
        rest: bytearray
    """

    damper_absorb       = FloatField(offset=0)
    field_4             = FloatField()
    field_8             = FloatField()
    field_12            = ArrayField(shape=(3, 3), elem_field_type=FloatField)
    field_48            = ArrayField(shape=(3, 3), elem_field_type=FloatField)
    field_84            = ArrayField(shape=3, elem_field_type=FloatField)
    field_108           = FloatField(offset=108)
    has_ground_contact  = BooleanField()
    contact_material_id = IntegerField()
    is_sliding          = BooleanField()
    relative_rotz_axis  = ArrayField(shape=3, elem_field_type=FloatField)
    nb_ground_contacts  = IntegerField(offset=140)
    field_144           = ArrayField(shape=3, elem_field_type=FloatField)
    rest                = ByteArrayField(12)


class WheelState(ByteStruct):
    """
    Attributes:
        rest: bytearray
    """

    rest = ByteArrayField(100, offset=0)


class SimulationWheel(ByteStruct):
    """
    Attributes:
        steerable: bool
        field_8: int
        surface_handler: SurfaceHandler
        field_112: np.ndarray
        field_160: int
        field_164: int
        offset_from_vehicle: np.ndarray
        real_time_state: RealTimeState
        field_348: int
        contact_relative_local_distance: np.ndarray
        prev_sync_wheel_state: WheelState
        sync_wheel_state: WheelState
        field_564: WheelState
        async_wheel_state: WheelState
    """

    steerable                       = BooleanField(offset=4)
    field_8                         = IntegerField()
    surface_handler                 = StructField(SurfaceHandler)
    field_112                       = ArrayField(shape=(4, 3), elem_field_type=FloatField)
    field_160                       = IntegerField()
    field_164                       = IntegerField()
    offset_from_vehicle             = ArrayField(shape=3, elem_field_type=FloatField)
    real_time_state                 = StructField(RealTimeState)
    field_348                       = IntegerField()
    contact_relative_local_distance = ArrayField(shape=3, elem_field_type=FloatField)
    prev_sync_wheel_state           = StructField(WheelState, instance_with_parent=False)
    sync_wheel_state                = StructField(WheelState, instance_with_parent=False)
    field_564                       = StructField(WheelState, instance_with_parent=False)
    async_wheel_state               = StructField(WheelState, instance_with_parent=False)


class CheckpointTime(ByteStruct):
    """
    Attributes:
        time: int
        stunts_score: int
    """

    time            = IntegerField(offset=0)
    stunts_score    = IntegerField()


class CheckpointData(ByteStruct):
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
    reserved            = IntegerField(offset=0)
    cp_states_length    = IntegerField()
    cp_states           = ArrayField(shape=None, elem_field_type=BooleanField)
    cp_times_length     = IntegerField()
    cp_times            = ArrayField(shape=None, elem_field_type=CheckpointTime)

    def __init__(self, *args, **kwargs):
        if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], list):
            super().__init__(**kwargs)
            self.cp_states = args[0]
            self.cp_states_length = len(args[0])
            self.cp_times = args[1]
            self.cp_times_length = len(args[1])
        else:
            super().__init__(*args, **kwargs)

    def read_from_file(self, file):
        self.data += file.read(self.cp_states_length * 4)
        self.resize(CheckpointData.cp_states_field, self.cp_states_length)

        self.data += file.read(self.cp_times_length * CheckpointTime.min_size)
        self.resize(CheckpointData.cp_times_field, self.cp_times_length)


class CachedInput(ByteStruct):
    """
    Attributes:
        time: int
        event: Event
    """

    time    = IntegerField(offset=0)
    event   = StructField(Event)


class SceneVehicleCarState(ByteStruct):
    """
    Attributes:
        speed_forward: float
        speed_sideward: float
        input_steer: float
        input_gas: float
        input_brake: float
        is_turbo: bool
        rpm: float
        gearbox_state: int
        rest: bytearray
    """

    speed_forward   = FloatField(offset=0)
    speed_sideward  = FloatField()
    input_steer     = FloatField()
    input_gas       = FloatField()
    input_brake     = FloatField()
    is_turbo        = BooleanField()
    rpm             = FloatField(offset=128)
    gearbox_state   = IntegerField(offset=136)
    rest            = ByteArrayField(28)


class Engine(ByteStruct):
    """
    Attributes:
        max_rpm: float
        braking_factor: float
        clamped_rpm: float
        actual_rpm: float
        slide_factor: float
        rear_gear: int
        gear: int
    """

    max_rpm         = FloatField(offset=0)
    braking_factor  = FloatField(offset=20)
    clamped_rpm     = FloatField()
    actual_rpm      = FloatField()
    slide_factor    = FloatField()
    rear_gear       = IntegerField(offset=40)
    gear            = IntegerField()


class SceneVehicleCar(ByteStruct):
    """
    Attributes:
        is_update_async: bool
        input_gas: float
        input_brake: float
        input_steer: float
        is_light_trials_set: bool
        horn_limit: int
        quality: int
        max_linear_speed: float
        gearbox_state: int
        block_flags: int
        prev_sync_vehicle_state: SceneVehicleCarState
        sync_vehicle_state: SceneVehicleCarState
        async_vehicle_state: SceneVehicleCarState
        prev_async_vehicle_state: SceneVehicleCarState
        engine: Engine
        has_any_lateral_contact: bool
        last_has_any_lateral_contact_time: int
        water_forces_applied: bool
        turning_rate: float
        turbo_boost_factor: float
        last_turbo_type_change_time: int
        last_turbo_time: int
        turbo_type: int
        roulette_value: int
        is_freewheeling: bool
        is_sliding: bool
        wheel_contact_absorb_counter: int
        burnout_state: int
        current_local_speed: np.ndarray
        total_central_force_added: np.ndarray
        is_rubber_ball: bool
        saved_state: np.ndarray
    """

    is_update_async                     = BooleanField(offset=76)
    input_gas                           = FloatField()
    input_brake                         = FloatField()
    input_steer                         = FloatField()
    is_light_trials_set                 = BooleanField(offset=116)
    horn_limit                          = IntegerField(offset=148)
    quality                             = IntegerField(offset=164)
    max_linear_speed                    = FloatField(offset=736)
    gearbox_state                       = IntegerField()
    block_flags                         = IntegerField()
    prev_sync_vehicle_state             = StructField(SceneVehicleCarState, instance_with_parent=False)
    sync_vehicle_state                  = StructField(SceneVehicleCarState, instance_with_parent=False)
    async_vehicle_state                 = StructField(SceneVehicleCarState, instance_with_parent=False)
    prev_async_vehicle_state            = StructField(SceneVehicleCarState, instance_with_parent=False)
    engine                              = StructField(Engine, offset=1436)
    has_any_lateral_contact             = BooleanField(offset=1500)
    last_has_any_lateral_contact_time   = IntegerField()
    water_forces_applied                = BooleanField()
    turning_rate                        = FloatField()
    turbo_boost_factor                  = FloatField(offset=1524)
    last_turbo_type_change_time         = IntegerField()
    last_turbo_time                     = IntegerField()
    turbo_type                          = IntegerField()
    roulette_value                      = FloatField(offset=1544)
    is_freewheeling                     = BooleanField()
    is_sliding                          = BooleanField(offset=1576)
    wheel_contact_absorb_counter        = IntegerField(offset=1660)
    burnout_state                       = IntegerField(offset=1692)
    current_local_speed                 = ArrayField(offset=1804, shape=3, elem_field_type=FloatField)
    total_central_force_added           = ArrayField(offset=2072, shape=3, elem_field_type=FloatField)
    is_rubber_ball                      = BooleanField(offset=2116)
    saved_state                         = ArrayField(shape=(4, 3), elem_field_type=FloatField)


class SimStateData(ByteStruct):
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

    Attributes:
        version: int
        context_mode: int
        flags: int
        timers: np.ndarray
        dyna: HmsDynaStruct
        scene_mobil: SceneVehicleCar
        simulation_wheels: np.ndarray
        plug_solid: bytes
        cmd_buffer_core: bytes
        player_info: PlayerInfoStruct
        internal_input_state: np.ndarray
        input_running_event: Event
        input_finish_event: Event
        input_accelerate_event: Event
        input_brake_event: Event
        input_left_event: Event
        input_right_event: Event
        input_steer_event: Event
        input_gas_event: Event
    """
    version                 = IntegerField(offset=0, signed=False)
    context_mode            = IntegerField(signed=False)
    flags                   = IntegerField(signed=False)
    timers                  = ArrayField(shape=53, elem_field_type=IntegerField)
    dyna                    = StructField(HmsDynaStruct, instance_with_parent=False)
    scene_mobil             = StructField(SceneVehicleCar, instance_with_parent=False)
    simulation_wheels       = ArrayField(shape=4, elem_field_type=SimulationWheel)
    plug_solid              = ByteArrayField(68)
    cmd_buffer_core         = ByteArrayField(264)
    player_info             = StructField(PlayerInfoStruct, instance_with_parent=False)
    internal_input_state    = ArrayField(shape=10, elem_field_type=CachedInput)

    input_running_event     = StructField(Event, instance_with_parent=False)
    input_finish_event      = StructField(Event, instance_with_parent=False)
    input_accelerate_event  = StructField(Event, instance_with_parent=False)
    input_brake_event       = StructField(Event, instance_with_parent=False)
    input_left_event        = StructField(Event, instance_with_parent=False)
    input_right_event       = StructField(Event, instance_with_parent=False)
    input_steer_event       = StructField(Event, instance_with_parent=False)
    input_gas_event         = StructField(Event, instance_with_parent=False)

    num_respawns            = IntegerField(signed=False)

    cp_data                 = StructField(CheckpointData, instance_with_parent=False)

    @property
    def time(self) -> int:
        if (self.flags & SIM_HAS_TIMERS) == 0:
            return 0

        return self.timers[1]

    @property
    def position(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]
        
        return list(self.dyna.current_state.position)

    @property
    def velocity(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]

        return list(self.dyna.current_state.linear_speed)

    # Available only in run context
    @property
    def display_speed(self) -> int:
        if (self.flags & SIM_HAS_PLAYER_INFO) == 0:
            return 0

        return self.player_info.display_speed

    @position.setter
    def position(self, pos: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.dyna.current_state.position = pos
        return True

    @velocity.setter
    def velocity(self, vel: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.dyna.current_state.linear_speed = pos
        return True

    @property
    def rotation_matrix(self) -> list:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [[0, 0, 0]] * 3

        return self.dyna.current_state.rotation.to_numpy()

    @rotation_matrix.setter
    def rotation_matrix(self, matrix: list) -> bool:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return False

        self.dyna.current_state.rotation = matrix

    @property
    def yaw_pitch_roll(self) -> np.array:
        if (self.flags & SIM_HAS_DYNA) == 0:
            return [0, 0, 0]

        mat = self.rotation_matrix
        return list(util.quat_to_ypw(util.mat3_to_quat(mat)))

    @property
    def race_time(self) -> int:
        if (self.flags & SIM_HAS_PLAYER_INFO) == 0:
            return False

        return self.player_info.race_time

    @property
    def rewind_time(self) -> int:
        return self.race_time + 10

    @property
    def input_accelerate(self) -> bool:
        return self.input_accelerate_event.binary_value

    @property
    def input_brake(self) -> bool:
        return self.input_brake_event.binary_value

    @property
    def input_left(self) -> bool:
        return self.input_left_event.binary_value

    @property
    def input_right(self) -> bool:
        return self.input_right_event.binary_value

    @property
    def input_steer(self) -> int:
        return self.input_steer_event.analog_value

    @property
    def input_gas(self) -> int:
        return self.input_gas_event.analog_value


class BFTarget(IntEnum):
    """
    The bruteforce metric that is being currently optimized.
    """
    FINISH_TIME = 0
    CHECKPOINT_TIME = 1
    TRIGGER = 2
    DISTANCE_SPEED = 3


class BFPhase(IntEnum):
    """
    The phase in which the bruteforce script is currently working.

    The initial phase is executed at the beginning of the process and after each improvement.
    It is used primarily for collecting data about the race e.g: the race time, position of the car,
    checkpoint times etc. No state modification happens at this state and it is recommended to use this phase
    to collect information about the current solution.

    The search phase is when TMInterface is searching for a new improvement. In this phase, the process
    changes inputs according to the user settings and evaluates the solution based on the current target.
    """
    INITIAL = 0
    SEARCH = 1


class BFEvaluationDecision(IntEnum):
    """
    The decision taken by the client in every bruteforce physics step.
    Returned in :meth:`Client.on_bruteforce_evaluate` in an BFEvaluationResponse instance.

    `CONTINUE`: run the default evaluation of the bruteforce script

    `DO_NOTHING`: do not run any evaluation that could result in accepting or rejecting the evaluated solution

    `ACCEPT`: accept the current solution as the new best one. Starts a new intial phase in the next physics step.

    `REJECT`: rejects the current solution and generates a new one for next evaluation

    `STOP`: stops the bruteforce script and lets the game simulate the race until the end
    """
    CONTINUE = 0
    DO_NOTHING = 1
    ACCEPT = 2
    REJECT = 3
    STOP = 4


class BFEvaluationInfo(ByteStruct):
    """
    The bruteforce settings applied in the bruteforce process, including the current simulation race time.
    """
    phase               = IntegerField(signed=False)
    target              = IntegerField(signed=False)
    time                = IntegerField()
    modified_inputs_num = IntegerField()
    inputs_min_time     = IntegerField()
    inputs_max_time     = IntegerField()
    max_steer_diff      = IntegerField()
    max_time_diff       = IntegerField()
    override_stop_time  = IntegerField()
    search_forever      = BooleanField()
    inputs_extend_steer = BooleanField()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not args:
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


class BFEvaluationResponse(ByteStruct):
    """
    The response object sent by :meth:`Client.on_bruteforce_evaluate`.
    
    If `decision` is set to :class:`BFEvaluationDecision.REJECT`,
    you are allowed to change the inputs manually via the :meth:`TMInterface.set_event_buffer` method and
    set the `rewind_time` to `timestamp - 10` where `timestamp` is the first input that has been
    changed by your algorithm. Otherwise, TMInterface will automatically randomize the inputs according
    to the current settings itself.
    """
    decision    = IntegerField(signed=False)
    rewind_time = IntegerField()

    def __init__(self) -> None:
        super().__init__()
        self.decision = BFEvaluationDecision.CONTINUE
        self.rewind_time = -1


class ClassicString(ByteStruct):
    """
    A string sent by the client to TMInterface.
    """
    command_length  = IntegerField()
    command         = StringField(None)

    def __init__(self, command: str) -> None:
        super().__init__()
        self.command_length = len(command)
        self.command = command
