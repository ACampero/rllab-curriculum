require_relative '../rocky/utils'

quantile = 1
seed = 1

params = {
  mdp: {
    _name: "box2d.double_pendulum_mdp",
    # _name: "box2d.car_parking_mdp",
    # _name: "box2d.cartpole_mdp",
    # trig_angle: false,
    # frame_skip: 2,
  },
  normalize_mdp: true,
  policy: {
    _name: "mean_std_nn_policy",
    hidden_sizes: [100, 50, 25],
    load_params: "data/ppo_double_skip2_pendulum_seed_1/itr_1.pkl",
    load_params_masks: [true, true, true, true, false, false,
                        false, false, false],
  },
  baseline: {
    _name: "linear_feature_baseline",
  },
  exp_name: "ppo_double_skip2_pendulum_seed_#{seed}",
  algo: {
    _name: "trpo",
    step_size: 0.05,
    whole_paths: true,
    batch_size: 10000,
    max_path_length: 100,
    n_itr: 500,
    plot: true,

  },
  n_parallel: 3,
  # snapshot_mode: "none",
  seed: seed,
  plot: true,
}
command = to_command(params)
puts command
system(command)

