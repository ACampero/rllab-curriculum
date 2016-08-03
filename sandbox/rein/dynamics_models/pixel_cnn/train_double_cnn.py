import sys
import time

import numpy as np
import tensorflow as tf

import nn
import plotting
import scopes
from utils import load_dataset_MNIST, load_dataset_Atari
import rllab.misc.logger as logger

sys.setrecursionlimit(10000)


class ExperimentPixelCNN(object):
    def plot_pred_imgs(self, model, inputs, targets, itr, count):
        # This is specific to Atari.
        import matplotlib.pyplot as plt
        if not hasattr(self, '_fig'):
            self._fig = plt.figure()
            self._fig_1 = self._fig.add_subplot(141)
            plt.tick_params(axis='both', which='both', bottom='off', top='off',
                            labelbottom='off', right='off', left='off', labelleft='off')
            self._fig_2 = self._fig.add_subplot(142)
            plt.tick_params(axis='both', which='both', bottom='off', top='off',
                            labelbottom='off', right='off', left='off', labelleft='off')
            self._fig_3 = self._fig.add_subplot(143)
            plt.tick_params(axis='both', which='both', bottom='off', top='off',
                            labelbottom='off', right='off', left='off', labelleft='off')
            self._fig_4 = self._fig.add_subplot(144)
            plt.tick_params(axis='both', which='both', bottom='off', top='off',
                            labelbottom='off', right='off', left='off', labelleft='off')
            self._im1, self._im2, self._im3, self._im4 = None, None, None, None

        idx = np.random.randint(0, inputs.shape[0], 1)
        sanity_pred = model.pred_fn(inputs)
        input_im = inputs
        input_im = input_im[idx, :].reshape((1, 84, 84)).transpose(1, 2, 0)[:, :, 0]
        sanity_pred_im = sanity_pred[idx, :-1]
        sanity_pred_im = sanity_pred_im.reshape((-1, model.num_classes))
        sanity_pred_im = np.argmax(sanity_pred_im, axis=1)
        sanity_pred_im = sanity_pred_im.reshape((1, 84, 84)).transpose(1, 2, 0)[:, :, 0]
        target_im = targets[idx, :].reshape((1, 84, 84)).transpose(1, 2, 0)[:, :, 0]

        sanity_pred_im = sanity_pred_im.astype(float) / float(model.num_classes)
        target_im = target_im.astype(float) / float(model.num_classes)
        input_im = input_im.astype(float) / float(model.num_classes)
        err = np.abs(target_im - sanity_pred_im)

        if self._im1 is None or self._im2 is None:
            self._im1 = self._fig_1.imshow(
                input_im, interpolation='none', cmap='Greys_r', vmin=0, vmax=1)
            self._im2 = self._fig_2.imshow(
                target_im, interpolation='none', cmap='Greys_r', vmin=0, vmax=1)
            self._im3 = self._fig_3.imshow(
                sanity_pred_im, interpolation='none', cmap='Greys_r', vmin=0, vmax=1)
            self._im4 = self._fig_4.imshow(
                err, interpolation='none', cmap='Greys_r', vmin=0, vmax=1)
        else:
            self._im1.set_data(input_im)
            self._im2.set_data(target_im)
            self._im3.set_data(sanity_pred_im)
            self._im4.set_data(err)
        plt.savefig(
            logger._snapshot_dir + '/dynpred_img_{}_{}.png'.format(itr, count), bbox_inches='tight')

    def main(self):

        seed = 1
        batch_size = 16
        init_batch_size = 100
        sample_batch_size = 1
        nr_resnet = 5
        nr_logistic_mix = 10
        nr_gpu = 1
        learning_rate = 0.003
        nr_filters = 16

        # load CIFAR-10 training data
        trainx, testx = load_dataset_Atari()
        im_size = trainx.shape[-1]
        trainx = np.transpose(trainx, (0, 2, 3, 1))
        trainx = np.concatenate((trainx, trainx, trainx), axis=3)
        nr_batches_train = int(trainx.shape[0] / batch_size)
        nr_batches_train_per_gpu = nr_batches_train / nr_gpu

        testx = np.transpose(testx, (0, 2, 3, 1))
        testx = np.concatenate((testx, testx, testx), axis=3)
        nr_batches_test = int(testx.shape[0] / batch_size)
        nr_batches_test_per_gpu = nr_batches_test / nr_gpu

        # //////////// perform training //////////////
        logger.log('Training ...')

        # fix random seed
        rng = np.random.RandomState(seed)

        # conditioning on pixels above and to the left
        def conditioner_spec(x, init=False, ema=None):
            counters = {}
            with scopes.arg_scope([nn.down_shifted_conv2d, nn.down_right_shifted_conv2d, nn.down_shifted_deconv2d,
                                   nn.down_right_shifted_deconv2d, nn.nin],
                                  counters=counters, init=init, ema=ema):

                # ////////// up pass ////////
                xs = nn.int_shape(x)
                x_pad = tf.concat(3,
                                  [x, tf.ones(
                                      xs[:-1] + [1])])  # add channel of ones to distinguish image from padding later on
                u_list = [nn.down_shifted_conv2d(x_pad, num_filters=nr_filters,
                                                 filter_size=[2, 3])]  # stream for current row + up
                ul_list = [
                    nn.down_shift(nn.down_shifted_conv2d(x_pad, num_filters=nr_filters, filter_size=[1, 3])) + \
                    nn.right_shift(nn.down_right_shifted_conv2d(x, num_filters=nr_filters,
                                                                filter_size=[2, 1]))]  # stream for up and to the left

                for rep in range(nr_resnet):
                    u_list.append(nn.gated_resnet(u_list[-1], conv=nn.down_shifted_conv2d))
                    ul_list.append(
                        nn.aux_gated_resnet(ul_list[-1], nn.down_shift(u_list[-1]), conv=nn.down_right_shifted_conv2d))

                u_list.append(nn.down_shifted_conv2d(u_list[-1], num_filters=nr_filters, stride=[2, 2]))
                ul_list.append(nn.down_right_shifted_conv2d(ul_list[-1], num_filters=nr_filters, stride=[2, 2]))

                for rep in range(nr_resnet):
                    u_list.append(nn.gated_resnet(u_list[-1], conv=nn.down_shifted_conv2d))
                    ul_list.append(
                        nn.aux_gated_resnet(ul_list[-1], nn.down_shift(u_list[-1]), conv=nn.down_right_shifted_conv2d))

                u_list.append(nn.down_shifted_conv2d(u_list[-1], num_filters=nr_filters, stride=[2, 2]))
                ul_list.append(nn.down_right_shifted_conv2d(ul_list[-1], num_filters=nr_filters, stride=[2, 2]))

                for rep in range(nr_resnet):
                    u_list.append(nn.gated_resnet(u_list[-1], conv=nn.down_shifted_conv2d))
                    ul_list.append(
                        nn.aux_gated_resnet(ul_list[-1], nn.down_shift(u_list[-1]), conv=nn.down_right_shifted_conv2d))

                # /////// down pass ////////
                u = u_list.pop()
                ul = ul_list.pop()

                for rep in range(nr_resnet):
                    u = nn.aux_gated_resnet(u, u_list.pop(), conv=nn.down_shifted_conv2d)
                    ul = nn.aux_gated_resnet(ul, tf.concat(3, [nn.down_shift(u), ul_list.pop()]),
                                             conv=nn.down_right_shifted_conv2d)

                u = nn.down_shifted_deconv2d(u, num_filters=nr_filters, stride=[2, 2])
                ul = nn.down_right_shifted_deconv2d(ul, num_filters=nr_filters, stride=[2, 2])

                for rep in range(nr_resnet + 1):
                    u = nn.aux_gated_resnet(u, u_list.pop(), conv=nn.down_shifted_conv2d)
                    ul = nn.aux_gated_resnet(ul, tf.concat(3, [nn.down_shift(u), ul_list.pop()]),
                                             conv=nn.down_right_shifted_conv2d)

                u = nn.down_shifted_deconv2d(u, num_filters=nr_filters, stride=[2, 2])
                ul = nn.down_right_shifted_deconv2d(ul, num_filters=nr_filters, stride=[2, 2])

                for rep in range(nr_resnet + 1):
                    u = nn.aux_gated_resnet(u, u_list.pop(), conv=nn.down_shifted_conv2d)
                    ul = nn.aux_gated_resnet(ul, tf.concat(3, [nn.down_shift(u), ul_list.pop()]),
                                             conv=nn.down_right_shifted_conv2d)

                x_out = nn.nin(nn.concat_elu(ul), 10 * nr_logistic_mix)

                assert len(u_list) == 0
                assert len(ul_list) == 0

            return x_out

        conditioner = tf.make_template('conditioner', conditioner_spec)

        # data
        x_init = tf.placeholder(tf.float32, shape=(init_batch_size, im_size, im_size, 3))

        # run once for data dependent initialization of parameters
        conditioner(x_init, init=True)

        # get list of all params
        all_params = tf.trainable_variables()

        # keep track of moving average
        ema = tf.train.ExponentialMovingAverage(decay=0.999)
        maintain_averages_op = tf.group(ema.apply(all_params))

        # sample from the model
        x_sample = tf.placeholder(tf.float32, shape=(sample_batch_size, im_size, im_size, 3))
        new_x_gen = nn.sample_from_discretized_mix_logistic(conditioner(x_sample, ema=ema), nr_logistic_mix)

        def sample_from_model(sess):
            x_gen = np.zeros((sample_batch_size, im_size, im_size, 3), dtype=np.float32)
            for yi in range(im_size):
                print(yi)
                for xi in range(im_size):
                    new_x_gen_np = sess.run(new_x_gen, {x_sample: x_gen})
                    x_gen[:, yi, xi, :] = new_x_gen_np[:, yi, xi, :].copy()
            return x_gen

        # get loss gradients over multiple GPUs
        xs = []
        grads = []
        loss = []
        loss_test = []
        for i in range(nr_gpu):
            xs.append(tf.placeholder(tf.float32, shape=(batch_size, im_size, im_size, 3)))

            # with tf.device('/gpu:%d' % i):
            with tf.device('/cpu:%d' % i):
                # train
                loss.append(-nn.discretized_mix_logistic(xs[i], conditioner(xs[i])))

                # gradients
                grads.append(tf.gradients(loss[i], all_params))

                # test
                loss_test.append(-nn.discretized_mix_logistic(xs[i], conditioner(xs[i], ema=ema)))

        # add gradients together and get training updates
        # with tf.device('/gpu:0'):
        with tf.device('/cpu:0'):
            for i in range(1, nr_gpu):
                loss[0] += loss[i]
                loss_test[0] += loss_test[i]
                for j in range(len(grads[0])):
                    grads[0][j] += grads[i][j]

            # training ops
            optimizer = nn.adamax_updates(all_params, grads[0], lr=learning_rate)

        # convert loss to bits / dim
        bits_per_dim = loss[0] / (nr_gpu * np.log(2.) * 3 * im_size * im_size * batch_size)

        # init & save
        initializer = tf.initialize_all_variables()
        saver = tf.train.Saver()

        begin_all = time.time()
        with tf.Session() as sess:
            for epoch in range(1000):
                begin = time.time()

                # randomly permute
                trainx = trainx[rng.permutation(trainx.shape[0])]

                # init
                if epoch == 0:
                    sess.run(initializer, {x_init: trainx[:init_batch_size]})

                # train
                train_loss = 0.
                for t in range(nr_batches_train_per_gpu):
                    feed_dict = {}
                    for i in range(nr_gpu):
                        td = t + i * nr_batches_train_per_gpu
                        feed_dict[xs[i]] = trainx[td * batch_size:(td + 1) * batch_size]
                    l, _ = sess.run([bits_per_dim, optimizer], feed_dict)
                    train_loss += l
                    print(l)
                    sess.run(maintain_averages_op)
                train_loss /= nr_batches_train_per_gpu

                print("Iteration %d, time = %ds, train bits_per_dim = %.4f" % (
                    epoch, time.time() - begin, train_loss))
                sys.stdout.flush()

                if epoch % 1 == 0:
                    # generate samples from the model
                    sample_x = sample_from_model(sess)
                    img_tile = plotting.img_tile(sample_x, aspect_ratio=1.0, border_color=1.0, stretch=True)
                    img = plotting.plot_img(img_tile, title='Atari 84x84')
                    plotting.plt.savefig(logger._snapshot_dir + '/dynpred_img_{}.png'.format(epoch))
                    plotting.plt.close('all')

                    # save params
                    saver.save(sess, logger._snapshot_dir + '/params.ckpt')