import numpy as np

from sandbox.young_clgan.gan.gan import FCGAN


class GoalGAN(object):
    """A GAN for generating goals. It is just a wrapper for clgan.GAN.FCGAN"""

    def __init__(self, goal_size, evaluater_size, goal_range,
                 goal_noise_level, goal_center=None, *args, **kwargs):
        self.gan = FCGAN(
            generator_output_size=goal_size,
            discriminator_output_size=evaluater_size,
            *args,
            **kwargs
        )
        self.goal_size = goal_size
        self.evaluater_size = evaluater_size
        self.goal_range = goal_range
        self.goal_center = np.array(goal_center) if goal_center is not None else np.zeros(goal_size)
        self.goal_noise_level = goal_noise_level
        print('goal_center is : ', self.goal_center, 'goal_range: ', self.goal_range)

    def pretrain_uniform(self, size=10000, outer_iters=10, generator_iters=5,
                         discriminator_iters=200):
        """
        :param size: number of uniformly sampled goals (that we will try to fit as output of the GAN)
        :param outer_iters: of the GAN
        """
        goals = self.goal_center + np.random.uniform(
            -self.goal_range, self.goal_range, size=(size, self.goal_size)
        )
        return self.pretrain(goals, outer_iters, generator_iters, discriminator_iters)

    def pretrain(self, goals, outer_iters=10, generator_iters=5,
                 discriminator_iters=200):
        """
        Pretrain the goal GAN to match the distribution of given goals.
        :param goals: the goal distribution to match
        :param outer_iters: of the GAN
        """
        labels = np.ones((goals.shape[0], self.evaluater_size))  # all goal same label --> uniform
        return self.train(
            goals, labels, outer_iters, generator_iters, discriminator_iters
        )

    def _add_noise_to_goals(self, goals):
        noise = np.random.randn(*goals.shape) * self.goal_noise_level
        goals += noise
        return np.clip(goals, self.goal_center - self.goal_range, self.goal_center + self.goal_range)

    def sample_goals(self, size):  # un-normalizes the goals
        normalized_goals, noise = self.gan.sample_generator(size)
        goals = self.goal_center + normalized_goals * self.goal_range
        return goals, noise

    def sample_goals_with_noise(self, size):
        goals, noise = self.sample_goals(size)
        goals = self._add_noise_to_goals(goals)
        return goals, noise

    def train(self, goals, labels, outer_iters, generator_iters,
              discriminator_iters, suppress_generated_goals=True):
        normalized_goals = (goals - self.goal_center) / self.goal_range
        return self.gan.train(
            normalized_goals, labels, outer_iters, generator_iters, discriminator_iters, suppress_generated_goals
        )

    def discriminator_predict(self, goals):
        return self.gan.discriminator_predict(goals)