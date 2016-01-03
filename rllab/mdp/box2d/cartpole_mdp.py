from rllab.mdp.box2d.box2d_mdp import Box2DMDP
from rllab.mdp.box2d.parser import find_body
import numpy as np
from rllab.core.serializable import Serializable
from rllab.misc import autoargs
from rllab.misc.overrides import overrides


class CartpoleMDP(Box2DMDP, Serializable):

    @autoargs.inherit(Box2DMDP.__init__)
    @autoargs.arg('position_only', type=bool,
                  help='Whether to only provide positions as the observation')
    def __init__(
            self,
            position_only=False,
            **kwargs):
        self.position_only = position_only
        self.max_pole_angle = .2
        self.max_cart_pos = 2.4
        self.max_cart_speed = 4.
        self.max_pole_speed = 4.
        super(CartpoleMDP, self).__init__(
            self.model_path("cartpole.xml"),
            **kwargs
        )
        self.cart = find_body(self.world, "cart")
        self.pole = find_body(self.world, "pole")
        Serializable.__init__(self, position_only=position_only)

    @overrides
    def reset(self):
        self._set_state(self.initial_state)
        bounds = np.array([
            self.max_cart_pos,
            self.max_cart_speed,
            self.max_pole_angle,
            self.max_pole_speed
        ])
        low, high = -0.05*bounds, 0.05*bounds
        xpos, xvel, apos, avel = np.random.uniform(low, high)
        self.cart.position = (xpos, self.cart.position[1])
        self.cart.linearVelocity = (xvel, self.cart.linearVelocity[1])
        self.pole.angle = apos
        self.pole.angularVelocity = avel
        return self.get_state(), self.get_current_obs()

    @overrides
    def get_current_obs(self):
        raw_obs = self.get_raw_obs()
        if self.position_only:
            return raw_obs[[0, 2]]
        else:
            return raw_obs

    @overrides
    def get_current_reward(
            self, state, raw_obs, action, next_state, next_raw_obs):
        notdone = 1 - int(self.is_current_done())
        ucost = 1e-5*(action**2).sum()
        xcost = 1 - np.cos(self.pole.angle)
        return notdone * 10 - notdone * xcost - notdone * ucost

    @overrides
    def is_current_done(self):
        return abs(self.cart.position[0]) > self.max_cart_pos or \
            abs(self.pole.angle) > self.max_pole_angle
