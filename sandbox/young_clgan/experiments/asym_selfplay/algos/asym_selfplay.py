import numpy as np

from rllab.algos.trpo import TRPO
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from rllab.envs.mujoco.maze.point_maze_env import PointMazeEnv
from rllab.policies.gaussian_mlp_policy import GaussianMLPPolicy
from rllab.sampler.utils import rollout
from sandbox.young_clgan.envs.base import UniformListStateGenerator, FixedStateGenerator
from sandbox.young_clgan.experiments.asym_selfplay.envs.stop_action_env import StopActionEnv


def update_rewards(paths_alice, paths_bob, gamma):
    assert len(paths_alice) == len(paths_bob), 'Error, both agents need an equal number of paths.'

    for path_alice, path_bob in zip(paths_alice, paths_bob):
        alice_bonus = 10
        alice_factor = 0.1
        t_alice = path_alice['rewards'].shape[0]
        t_bob = path_bob['rewards'].shape[0]
        path_alice['rewards'] = np.zeros_like(path_alice['rewards'])
        path_bob['rewards'] = np.zeros_like(path_bob['rewards'])
        #path_alice['rewards'][-1] = gamma * np.max([0, t_bob + alice_bonus - t_alice])
        path_alice['rewards'][-1] = gamma * max(0, alice_bonus + t_bob - alice_factor * t_alice)
        path_bob['rewards'][-1] = -gamma * t_bob

    return paths_alice, paths_bob


class AsymSelfplay(object):

    def __init__(self, algo_alice, algo_bob, env_alice, env_bob, policy_alice, policy_bob, start_states,
                 num_rollouts=10, gamma = 0.1):
        self.algo_alice = algo_alice
        self.algo_bob = algo_bob
        self.env_alice = env_alice
        self.env_bob = env_bob
        self.policy_alice = policy_alice
        self.policy_bob = policy_bob

        self.max_path_length = algo_alice.max_path_length
        self.num_rollouts = num_rollouts
        self.gamma = gamma
        self.optimize_alice = True
        self.optimize_bob = False
        self.start_states = start_states

    def optimize(self, iter=0):

        # get paths
        n_starts = len(self.start_states)

        for itr in range(self.algo_alice.n_itr):

            paths_alice = []
            paths_bob = []
            new_start_states = []

            for i in range(self.num_rollouts):
                self.env_alice.update_start_generator(FixedStateGenerator(self.start_states[i % n_starts]))

                paths_alice.append(rollout(self.env_alice, self.policy_alice, max_path_length=self.max_path_length,
                                           animated=False))

                alice_end_obs = paths_alice[i]['observations'][-1]
                new_start_state = self.env_alice._obs2start_transform(alice_end_obs)
                new_start_states.append(new_start_state)

                self.env_bob.update_start_generator(FixedStateGenerator(new_start_state))
                paths_bob.append(rollout(self.env_bob, self.policy_bob, max_path_length=self.max_path_length,
                                         animated=False))

            # update rewards
            paths_alice, paths_bob = update_rewards(paths_alice=paths_alice, paths_bob=paths_bob, gamma=self.gamma)

            # optimize policies
            if self.optimize_alice:
                self.algo_alice.start_worker()
                self.algo_alice.init_opt()
                training_samples_alice = self.algo_alice.sampler.process_samples(itr=iter, paths=paths_alice)
                self.algo_alice.optimize_policy(itr=iter, samples_data=training_samples_alice)

            if self.optimize_bob:
                self.algo_bob.start_worker()
                self.algo_bob.init_opt()
                training_samples_bob = self.algo_bob.sampler.process_samples(itr=iter, paths=paths_bob)
                self.algo_bob.optimize_policy(itr=iter, samples_data=training_samples_bob)

        return np.array(new_start_states)


if __name__ == '__main__':
    # aym selfplay only uses a single rollout
    # batching should be more stable
    num_rollouts = 50
    iterations = 10
    max_path_length = 100
    # they use a gamma between 0.1 and 0.01
    gamma = 0.01

    # todo setup the correct environments (correct wrappers for arbitrary reset)
    env_a1 = PointMazeEnv()
    env_a2 = StopActionEnv(PointMazeEnv())

    policy_a1 = GaussianMLPPolicy(
            env_spec=env_a1.spec,
            hidden_sizes=(64, 64),
            std_hidden_sizes=(16, 16)
    )

    policy_a2 = GaussianMLPPolicy(
            env_spec=env_a2.spec,
            hidden_sizes=(64, 64),
            std_hidden_sizes=(16, 16)
    )

    baseline_a1 = LinearFeatureBaseline(env_spec=env_a1.spec)
    baseline_a2 = LinearFeatureBaseline(env_spec=env_a2.spec)


    # They use discrete policy gradient but we should compare based on the same optimiser as TRPO tends to be mroe robust
    # Their algo: R. J. Williams. Simple statistical gradient-following algorithms for connectionist reinforcement
    # learning. In Machine Learning, pages 229–256, 1992.

    algo_a1 = TRPO(
        env=env_a1,
        policy=policy_a1,
        baseline=baseline_a1,
        batch_size=4000,
        max_path_length=max_path_length,
        n_itr=40,
        discount=0.99,
        step_size=0.01,
        # plot=True,
    )

    algo_a2 = TRPO(
        env=env_a2,
        policy=policy_a2,
        baseline=baseline_a2,
        batch_size=4000,
        max_path_length=max_path_length,
        n_itr=40,
        discount=0.99,
        step_size=0.01,
        # plot=True,
    )

    asym_selfplay = AsymSelfplay(algo_alice=algo_a1, algo_bob=algo_a2, num_rollouts=num_rollouts, gamma = gamma)

    for i in range(iterations):
        asym_selfplay.optimize(i)
    print('Done')