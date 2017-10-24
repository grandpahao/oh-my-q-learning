import numpy as np
import tensorflow as tf
from estimator import Estimator


class DistributionEstimator(Estimator):
    def __init__(self,
                 action_n,
                 vmin=-10,
                 vmax=10,
                 N=51,
                 summary_dir=None,
                 network=None,
                 x_shape=[None, 84, 84, 4],
                 scope="estimator"):
        self.vmin = vmin
        self.vamx = vmax
        self.N = N
        self.split_points = np.linspace(vmin, vmax, N)
        self.delta = (vmax - vmin) / (N - 1)
        super(DistributionEstimator, self).__init__(action_n, summary_dir,
                                                    network, x_shape, scope)

    def _build_model(self):
        """Builds the Tensorflow graph."""
        with tf.variable_scope(self.scope):
            self.X_pl = tf.placeholder(
                shape=self.x_shape, dtype=tf.float32, name="X")
            self.actions_pl = tf.placeholder(
                shape=[None], dtype=tf.int32, name="actions")
            self.y_pl = tf.placeholder(
                shape=[None, self.N], dtype=tf.float32, name="y")

            fc = self.network(self.X_pl)

            batch_size = tf.shape(self.X_pl)[0]
            logits = tf.contrib.layers.fully_connected(
                fc, self.action_n * self.N, activation_fn=None)
            self.probs = tf.nn.softmax(
                tf.reshape(logits, [-1, self.action_n, self.N]))

            gather_indices = tf.range(
                batch_size) * self.action_n + self.actions_pl
            self.action_probs = tf.gather(
                tf.reshape(self.probs, [-1, self.N]), gather_indices)

            self.losses = -tf.reduce_sum(
                self.y_pl * tf.log(self.action_probs), axis=-1)
            self.loss = tf.reduce_mean(self.losses)

            self.optimizer = tf.train.RMSPropOptimizer(0.00025, 0.99, 0.0,
                                                       1e-6)
            self.train_op = self.optimizer.minimize(
                self.loss, global_step=tf.contrib.framework.get_global_step())

            self.summaries = tf.summary.merge([
                tf.summary.scalar("loss", self.loss),
                tf.summary.histogram("loss_hist", self.losses),
                tf.summary.scalar("max_loss", tf.reduce_max(self.losses))
            ])

    def dis_predict(self, sess, s):
        probs = sess.run(self.probs, {self.X_pl: s})
        predictions = np.sum(probs * self.split_points, axis=-1)
        return probs, predictions

    def predict(self, sess, s):
        _, predictions = self.dis_predict(sess, s)
        return predictions
