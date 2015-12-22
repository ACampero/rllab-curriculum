from rllab.mdp.box2d.box2d_mdp import Box2DMDP
from rllab.mdp.box2d.parser import find_body
import numpy as np
from rllab.core.serializable import Serializable
from rllab.misc.overrides import overrides


class HopperMDP(Box2DMDP, Serializable):

    def __init__(self):
        super(HopperMDP, self).__init__(self.model_path("hopper.xml"))
        Serializable.__init__(self)
        self.torso = find_body(self.world, "torso")
        self.thigh = find_body(self.world, "thigh")
        self.leg = find_body(self.world, "leg")
        self.foot = find_body(self.world, "foot")

    @overrides
    def get_current_obs(self):
        raw_obs = self.get_raw_obs()
        # remove the x position from the observation
        return raw_obs[1:]

    @overrides
    def step(self, state, action):
        xprev = self.get_raw_obs()[0]
        next_state = self.forward_dynamics(state, action,
                                           restore=False)
        self.invalidate_state_caches()
        xafter = self.get_raw_obs()[0]
        reward = xafter - xprev
        done = self.is_current_done()
        next_obs = self.get_current_obs()
        return next_state, next_obs, reward, done

    # @overrides
    # def get_current_reward(self, state, action, next_state):
    #     if self.is_current_done():
    #         return 0
    #     raw_obs = self.get_raw_obs()
    #     print "xvel:", raw_obs[5], "xpos:", raw_obs[0]
    #     return raw_obs[5]

    @overrides
    def is_current_done(self):
        raw_obs = self.get_raw_obs()
        # TODO add the condition for forward pitch
        notdone = np.isfinite(raw_obs).all() and \
            (np.abs(raw_obs[1:]) < 100).all() and \
            (self.torso.position[1] > 0.7)
        return not notdone
