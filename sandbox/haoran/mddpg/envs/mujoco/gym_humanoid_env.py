from mujoco_py import glfw
import numpy as np
from gym.envs.mujoco import mujoco_env
from gym import utils
from sandbox.haoran.mddpg.misc.mujoco_utils import convert_gym_space

def mass_center(model):
    mass = model.body_mass
    xpos = model.data.xipos
    return (np.sum(mass * xpos, 0) / np.sum(mass))[0]

class HumanoidEnv(mujoco_env.MujocoEnv, utils.EzPickle):
    def __init__(self):
        mujoco_env.MujocoEnv.__init__(self, 'humanoid.xml', 5)
        utils.EzPickle.__init__(self)
        self.observation_space = convert_gym_space(self.observation_space)
        self.action_space = convert_gym_space(self.action_space)

    def _get_obs(self):
        data = self.model.data
        return np.concatenate([data.qpos.flat[2:],
                               data.qvel.flat,
                               data.cinert.flat,
                               data.cvel.flat,
                               data.qfrc_actuator.flat,
                               data.cfrc_ext.flat])

    def _step(self, a):
        pos_before = mass_center(self.model)
        self.do_simulation(a, self.frame_skip)
        pos_after = mass_center(self.model)
        alive_bonus = 5.0
        data = self.model.data
        lin_vel_cost = 0.25 * (pos_after - pos_before) / self.model.opt.timestep
        quad_ctrl_cost =  0.1 * np.square(data.ctrl).sum()
        quad_impact_cost = .5e-6 * np.square(data.cfrc_ext).sum()
        quad_impact_cost = min(quad_impact_cost, 10)
        reward = lin_vel_cost - quad_ctrl_cost - quad_impact_cost + alive_bonus
        qpos = self.model.data.qpos
        done = bool((qpos[2] < 1.0) or (qpos[2] > 2.0))
        com = self.get_body_com("torso")
        return self._get_obs(), reward, done, dict(reward_linvel=lin_vel_cost, reward_quadctrl=-quad_ctrl_cost, reward_alive=alive_bonus, reward_impact=-quad_impact_cost, com=com)

    def reset_model(self):
        c = 0.01
        self.set_state(
            self.init_qpos + np.random.uniform(low=-c, high=c, size=self.model.nq),
            self.init_qvel + np.random.uniform(low=-c, high=c, size=self.model.nv,)
        )
        return self._get_obs()

    def viewer_setup(self):
        self.viewer.cam.trackbodyid = 1
        self.viewer.cam.distance = self.model.stat.extent * 1.0
        self.viewer.cam.lookat[2] += .8
        self.viewer.cam.elevation = -20
        glfw.set_window_pos(self.viewer.window,1000,0)

    def get_param_values(self):
        return None

    def set_param_values(self, params):
        pass

    def log_stats(self, alg, epoch, paths, ax):
        # forward distance
        progs = []
        for path in paths:
            coms = path["env_infos"]["com"]
            progs.append(coms[-1][0] - coms[0][0])
            # x-coord of com at the last time step minus the 1st step

        stats = {
            'env: ForwardProgressAverage': np.mean(progs),
            'env: ForwardProgressMax': np.max(progs),
            'env: ForwardProgressMin': np.min(progs),
            'env: ForwardProgressStd': np.std(progs),
            'env: ForwardProgressDiff': np.max(progs) - np.min(progs),
        }

        HumanoidEnv.plot_paths(paths, ax)

        return stats

    @staticmethod
    def plot_paths(paths, ax):
        for path in paths:
            com = path['env_infos']['com']
            xx = com[:, 0]
            zz = com[:, 2]
            ax.plot(xx, zz, 'b')
        ax.set_xlim((np.min(xx) - 1, np.max(xx)+1))
        ax.set_ylim((-1, 2))

    def terminate(self):
        pass