# ---
# jupyter:
#   accelerator: GPU
#   colab:
#     collapsed_sections: []
#     name: Habitat Interactive Tasks
#     provenance: []
#     toc_visible: true
#   jupytext:
#     cell_metadata_filter: -all
#     formats: nb_python//py:percent,colabs//ipynb
#     notebook_metadata_filter: all
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.3
#   kernelspec:
#     display_name: Python [conda env:hab_merge] *
#     language: python
#     name: conda-env-hab_merge-py
#   language_info:
#     codemirror_mode:
#       name: ipython
#       version: 3
#     file_extension: .py
#     mimetype: text/x-python
#     name: python
#     nbconvert_exporter: python
#     pygments_lexer: ipython3
#     version: 3.6.13
# ---

# %%
# @title Installation { display-mode: "form" }
# @markdown (double click to show code).
# !curl -L https://raw.githubusercontent.com/facebookresearch/habitat-sim/main/examples/colab_utils/colab_install.sh | NIGHTLY=true bash -s
# %env HABLAB_BASE_CFG_PATH=/content/habitat-lab

# %%
import gym
import gym.spaces as spaces
import numpy as np

import habitat
import habitat_baselines.utils.gym_definitions  # noqa: F401
from habitat.core.embodied_task import Measure
from habitat.core.registry import registry
from habitat.core.simulator import Sensor, SensorTypes
from habitat.tasks.rearrange.rearrange_sensors import RearrangeReward
from habitat.tasks.rearrange.rearrange_task import RearrangeTask
from habitat.utils.visualizations.utils import observations_to_image
from habitat_baselines.utils.render_wrapper import overlay_frame
from habitat_sim.utils import viz_utils as vut

# %%
def insert_render_options(config):
    config.defrost()
    config.SIMULATOR.THIRD_RGB_SENSOR.WIDTH = 512
    config.SIMULATOR.THIRD_RGB_SENSOR.HEIGHT = 512
    config.SIMULATOR.AGENT_0.SENSORS.append("THIRD_RGB_SENSOR")
    config.SIMULATOR.DEBUG_RENDER = True
    config.freeze()
    return config


# %% [markdown]
# # Local installation
#
# For Habitat 2.0 functionality, install the `hab_suite` branch of Habitat Lab. Complete installation steps:
#
# 1. Install [Habitat Sim](https://github.com/facebookresearch/habitat-sim#recommended-conda-packages) **using the `withbullet` option**. For example: `conda install habitat-sim withbullet headless -c conda-forge -c aihabitat-nightly`.
# 2. Download the `hab_suite` branch of Habitat Lab: `git clone -b hab_suite https://github.com/facebookresearch/habitat-lab.git`
# 3. Install Habitat Lab: `cd habitat-lab && pip install -r requirements.txt && python setup.py develop --all`

# %% [markdown]
# # Quickstart
#
# Start with a minimal environment interaction loop using the Habitat API.

# %%
with habitat.Env(
    config=insert_render_options(
        habitat.get_config("../../../configs/tasks/rearrange/pick.yaml")
    )
) as env:
    observations = env.reset()  # noqa: F841

    print("Agent acting inside environment.")
    count_steps = 0
    # To save the video
    video_file_path = "data/example_interact.mp4"
    video_writer = vut.get_fast_video_writer(video_file_path, fps=30)

    while not env.episode_over:
        observations = env.step(env.action_space.sample())  # noqa: F841
        info = env.get_metrics()

        render_obs = observations_to_image(observations, info)
        render_obs = overlay_frame(render_obs, info)

        video_writer.append_data(render_obs)

        count_steps += 1
    print("Episode finished after {} steps.".format(count_steps))

    video_writer.close()
    if vut.is_notebook():
        vut.display_video(video_file_path)


# %% [markdown]
# ## Gym API
# You can also use environments through the Gym API.

# %%
env = gym.make("HabitatGymRenderPick-v0")

video_file_path = "data/example_interact.mp4"
video_writer = vut.get_fast_video_writer(video_file_path, fps=30)

done = False
env.reset()
while not done:
    obs, reward, done, info = env.step(env.action_space.sample())
    video_writer.append_data(env.render(mode="rgb_array"))

video_writer.close()
if vut.is_notebook():
    vut.display_video(video_file_path)


# %% [markdown]
# ## Interactive Play Script
# On your local machine with a display connected, play the tasks using the keyboard to control the robot:
# ```
# python examples/interactive_play.py --cfg configs/tasks/rearrange/composite.yaml --play-task --never-end
# ```
# For more information about the interactive play script, see the [documentation string at the top of the file](https://github.com/facebookresearch/habitat-lab/blob/hab_suite/examples/interactive_play.py).

# %% [markdown]
# ## Training with Habitat Baselines
# Start training policies with PPO using [Habitat Baselines](https://github.com/facebookresearch/habitat-lab/tree/main/habitat_baselines#baselines). As an example, start training a pick policy with:
#
# ```
# python -u habitat_baselines/run.py --exp-config habitat_baselines/config/rearrange/ddppo_pick.yaml --run-type train
# ```
# Find the [complete list of RL configurations here](https://github.com/facebookresearch/habitat-lab/tree/hab_suite/habitat_baselines/config/rearrange), any config starting with `ddppo` can be substituted.
#
# See [here](https://github.com/facebookresearch/habitat-lab/tree/main/habitat_baselines#baselines) for more information on how to run with Habitat Baselines.

# %% [markdown]
# # Defining New Tasks
# We will define a new task to navigate to an object and then pick it up.

# %%
@registry.register_task(name="RearrangeNavPickTask-v0")
class NavPickTaskV1(RearrangeTask):
    def reset(self, episode):
        self.target_object_index = np.random.randint(
            0, self._sim.get_n_targets()
        )
        start_pos = self._sim.pathfinder.get_random_navigable_point()
        self._sim.robot.base_pos = start_pos

        # Put any task reset logic here.
        return super().reset(episode)


@registry.register_sensor
class TargetStartSensor(Sensor):
    """
    Relative position from end effector to target object start position.
    """

    cls_uuid: str = "relative_object_to_end_effector"

    def __init__(self, sim, config, *args, task, **kwargs):
        self._sim = sim
        self._task = task
        self._config = config
        super().__init__(**kwargs)

    def _get_uuid(self, *args, **kwargs):
        return TargetStartSensor.cls_uuid

    def _get_sensor_type(self, *args, **kwargs):
        return SensorTypes.TENSOR

    def _get_observation_space(self, *args, **kwargs):
        return spaces.Box(
            shape=(3,),
            low=np.finfo(np.float32).min,
            high=np.finfo(np.float32).max,
            dtype=np.float32,
        )

    def get_observation(self, observations, episode, *args, **kwargs):
        global_T = self._sim.robot.ee_transform
        T_inv = global_T.inverted()
        start_pos = self._sim.get_target_objs_start()[
            self._task.target_object_index
        ]
        relative_start_pos = T_inv.transform_point(start_pos)
        return relative_start_pos


@registry.register_measure
class DistanceToTargetObject(Measure):
    """
    Gets the Euclidean distance to the target object from the end-effector.
    """

    cls_uuid: str = "distance_to_object"

    def __init__(self, sim, config, *args, **kwargs):
        self._sim = sim
        self._config = config
        super().__init__(**kwargs)

    @staticmethod
    def _get_uuid(*args, **kwargs):
        return DistanceToTargetObject.cls_uuid

    def reset_metric(self, *args, episode, **kwargs):
        self.update_metric(*args, episode=episode, **kwargs)

    def update_metric(self, *args, task, episode, **kwargs):
        ee_pos = self._sim.robot.ee_transform.translation

        idxs, _ = self._sim.get_targets()
        scene_pos = self._sim.get_scene_pos()[idxs[task.target_object_index]]

        self._metric = np.linalg.norm(scene_pos - ee_pos, ord=2, axis=-1)


@registry.register_measure
class NavPickReward(RearrangeReward):
    cls_uuid: str = "navpick_reward"

    def __init__(self, sim, config, *args, **kwargs):
        self._sim = sim
        self._config = config
        super().__init__(**kwargs)

    @staticmethod
    def _get_uuid(*args, **kwargs):
        return NavPickReward.cls_uuid

    def reset_metric(self, *args, task, episode, **kwargs):
        task.measurements.check_measure_dependencies(
            self.uuid,
            [
                DistanceToTargetObject.cls_uuid,
            ],
        )
        self.update_metric(*args, episode=episode, **kwargs)

    def update_metric(self, *args, task, episode, **kwargs):
        ee_to_object_distance = task.measurements.measures[
            DistanceToTargetObject.cls_uuid
        ].get_metric()

        self._metric = -ee_to_object_distance


@registry.register_measure
class NavPickSuccess(Measure):
    cls_uuid: str = "navpick_success"

    def __init__(self, sim, config, *args, **kwargs):
        self._sim = sim
        self._config = config
        self._prev_ee_pos = None
        super().__init__(**kwargs)

    @staticmethod
    def _get_uuid(*args, **kwargs):
        return NavPickSuccess.cls_uuid

    def reset_metric(self, *args, episode, task, observations, **kwargs):
        self.update_metric(
            *args,
            episode=episode,
            task=task,
            observations=observations,
            **kwargs
        )

    def update_metric(self, *args, episode, task, observations, **kwargs):
        # Is the agent holding the object and it's at the start?
        abs_targ_obj_idx = self._sim.scene_obj_ids[task.target_object_index]

        # Check that we are holding the right object and the object is actually
        # being held.
        self._metric = abs_targ_obj_idx == self._sim.grasp_mgr.snap_idx


# %% [markdown]
# ## Load as Habitat Task

# %%
cfg_txt = """
ENVIRONMENT:
    MAX_EPISODE_STEPS: 200
DATASET:
    TYPE: RearrangeDataset-v0
    SPLIT: train
    DATA_PATH: data/datasets/rearrange_pick/replica_cad/v0/rearrange_pick_replica_cad_v0/pick.json.gz
    SCENES_DIR: "data/replica_cad/"
TASK:
    TYPE: RearrangeNavPickTask-v0
    MAX_COLLISIONS: -1.0
    COUNT_OBJ_COLLISIONS: True
    COUNT_ROBOT_OBJ_COLLS: False
    DESIRED_RESTING_POSITION: [0.5, 0.0, 1.0]

    # In radians
    CONSTRAINT_VIOLATE_SHOULD_END: True

    # Sensors
    TARGET_START_SENSOR:
        TYPE: "TargetStartSensor"
    JOINT_SENSOR:
        TYPE: "JointSensor"
        DIMENSIONALITY: 7
    SENSORS: ["TARGET_START_SENSOR", "JOINT_SENSOR"]
    
    # Measurements
    ROBOT_FORCE:
        TYPE: "RobotForce"
        MIN_FORCE: 20.0
    FORCE_TERMINATE:
        TYPE: "ForceTerminate"
        MAX_ACCUM_FORCE: 5000.0
    ROBOT_COLLS:
        TYPE: "RobotCollisions"
    DISTANCE_TO_TARGET_OBJECT:
        TYPE: "DistanceToTargetObject"
    NAV_PICK_REWARD:
        TYPE: "NavPickReward"
        SCALING_FACTOR: 0.1

        # General Rearrange Reward config
        CONSTRAINT_VIOLATE_PEN: 10.0
        FORCE_PEN: 0.001
        MAX_FORCE_PEN: 1.0
        FORCE_END_PEN: 10.0
        
    NAV_PICK_REWARD:
        TYPE: "NavPickSuccess"
        SUCC_THRESH: 0.15

    MEASUREMENTS:
        - "ROBOT_FORCE"
        - "FORCE_TERMINATE"
        - "ROBOT_COLLS"
        - "DISTANCE_TO_TARGET_OBJECT"
        - "NAV_PICK_REWARD"
        - "NAV_PICK_REWARD"
    ACTIONS:
        # Defining the action space.
        ARM_ACTION:
            TYPE: "ArmAction"
            ARM_CONTROLLER: "ArmRelPosAction"
            GRIP_CONTROLLER: "MagicGraspAction"
            ARM_JOINT_DIMENSIONALITY: 7
            GRASP_THRESH_DIST: 0.15
            DISABLE_GRIP: False
            DELTA_POS_LIMIT: 0.0125
            EE_CTRL_LIM: 0.015
        BASE_VELOCITY:
            TYPE: "BaseVelAction"
            LIN_SPEED: 12.0
            ANG_SPEED: 12.0
            ALLOW_DYN_SLIDE: True
            END_ON_STOP: False
            ALLOW_BACK: True
            MIN_ABS_LIN_SPEED: 1.0
            MIN_ABS_ANG_SPEED: 1.0
    POSSIBLE_ACTIONS:
        - ARM_ACTION
        - BASE_VELOCITY

SIMULATOR:
    DEBUG_RENDER: False
    ACTION_SPACE_CONFIG: v0
    AGENTS: ['AGENT_0']
    ROBOT_JOINT_START_NOISE: 0.0
    AGENT_0:
        HEIGHT: 1.5
        IS_SET_START_STATE: False
        RADIUS: 0.1
        SENSORS: ['HEAD_RGB_SENSOR', 'HEAD_DEPTH_SENSOR', 'ARM_RGB_SENSOR', 'ARM_DEPTH_SENSOR']
        START_POSITION: [0, 0, 0]
        START_ROTATION: [0, 0, 0, 1]
    HEAD_RGB_SENSOR:
        WIDTH: 128
        HEIGHT: 128
    HEAD_DEPTH_SENSOR:
        WIDTH: 128
        HEIGHT: 128
        MIN_DEPTH: 0.0
        MAX_DEPTH: 10.0
        NORMALIZE_DEPTH: True
    ARM_DEPTH_SENSOR:
        HEIGHT: 128
        MAX_DEPTH: 10.0
        MIN_DEPTH: 0.0
        NORMALIZE_DEPTH: True
        WIDTH: 128
    ARM_RGB_SENSOR:
        HEIGHT: 128
        WIDTH: 128

    # Agent setup
    ARM_REST: [0.6, 0.0, 0.9]
    CTRL_FREQ: 120.0
    AC_FREQ_RATIO: 4
    ROBOT_URDF: ./data/robots/hab_fetch/robots/hab_fetch.urdf
    ROBOT_TYPE: "FetchRobot"
    FORWARD_STEP_SIZE: 0.25

    # Grasping
    HOLD_THRESH: 0.09
    GRASP_IMPULSE: 1000.0

    DEFAULT_AGENT_ID: 0
    HABITAT_SIM_V0:
        ALLOW_SLIDING: True
        ENABLE_PHYSICS: True
        GPU_DEVICE_ID: 0
        GPU_GPU: False
        PHYSICS_CONFIG_FILE: ./data/default.physics_config.json
    SEED: 100
    SEMANTIC_SENSOR:
        HEIGHT: 480
        HFOV: 90
        ORIENTATION: [0.0, 0.0, 0.0]
        POSITION: [0, 1.25, 0]
        TYPE: HabitatSimSemanticSensor
        WIDTH: 640
    TILT_ANGLE: 15
    TURN_ANGLE: 10
    TYPE: RearrangeSim-v0
"""
nav_pick_cfg_path = "data/nav_pick_demo.yaml"
with open(nav_pick_cfg_path, "w") as f:
    f.write(cfg_txt)

# %%
with habitat.Env(
    config=insert_render_options(habitat.get_config(nav_pick_cfg_path))
) as env:
    env.reset()

    print("Agent acting inside environment.")
    count_steps = 0
    # To save the video
    video_file_path = "data/example_interact.mp4"
    video_writer = vut.get_fast_video_writer(video_file_path, fps=30)

    while not env.episode_over:
        action = env.action_space.sample()
        observations = env.step(action)  # noqa: F841
        info = env.get_metrics()

        render_obs = observations_to_image(observations, info)
        render_obs = overlay_frame(render_obs, info)

        video_writer.append_data(render_obs)

        count_steps += 1
    print("Episode finished after {} steps.".format(count_steps))

    video_writer.close()
    if vut.is_notebook():
        vut.display_video(video_file_path)