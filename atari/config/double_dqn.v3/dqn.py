import os
import time
import traceback
import numpy as np
import tensorflow as tf
from util import Memory
from collections import defaultdict


class ResultsBuffer(object):
    def __init__(self):
        self.buffer = defaultdict(list)

    def update(self, info):
        for key in info:
            msg = info[key]
            self.buffer['reward'].append(msg[b'reward'])
            self.buffer['length'].append(msg[b'length'])
            if b'real_reward' in msg:
                self.buffer['real_reward'].append(msg[b'real_reward'])
                self.buffer['real_length'].append(msg[b'real_length'])

    def record(self, summary_writer, total_t, time):
        if self.buffer:
            reward = np.mean(self.buffer['reward'])
            length = np.mean(self.buffer['length'])
            self.buffer['reward'].clear()
            self.buffer['length'].clear()
            if 'real_reward' in self.buffer:
                real_reward = np.mean(self.buffer['real_reward'])
                real_length = np.mean(self.buffer['real_length'])
                self.buffer['real_reward'].clear()
                self.buffer['real_length'].clear()
            else:
                real_reward = None
            summary = tf.Summary()
            summary.value.add(simple_value=time, tag='time')
            summary.value.add(simple_value=reward, tag='results/reward')
            summary.value.add(simple_value=length, tag='results/length')
            if real_reward is not None:
                summary.value.add(
                    simple_value=real_reward, tag='results/real_reward')
                summary.value.add(
                    simple_value=real_length, tag='results/real_length')

            summary_writer.add_summary(summary, total_t)
            summary_writer.flush()


def dqn(sess,
        env,
        estimator,
        batch_size,
        summary_writer,
        checkpoint_path,
        exploration_policy_fn,
        discount_factor=0.99,
        save_model_every=1000,
        update_target_every=1,
        learning_starts=100,
        memory_size=100000,
        num_iterations=500000):

    saver = tf.train.Saver(max_to_keep=50)
    latest_checkpoint = tf.train.latest_checkpoint(checkpoint_path)
    if latest_checkpoint:
        print("Loading model checkpoint {}...".format(latest_checkpoint))
        try:
            saver.restore(sess, latest_checkpoint)
        except Exception:
            print('Loading failed, we will Start from scratch!!')

    total_t = sess.run(tf.train.get_global_step())

    memory_buffer = Memory(memory_size)
    results_buffer = ResultsBuffer()

    try:
        states = env.reset()
        for i in range(learning_starts):
            q_values = estimator.predict(sess, states)
            actions = exploration_policy_fn(q_values, total_t)
            next_states, rewards, dones, _ = env.step(actions)

            memory_buffer.extend(
                zip(states, actions, rewards, next_states, dones))
            states = next_states

        states = env.reset()

        start = time.time()
        for i in range(num_iterations):
            q_values = estimator.predict(sess, states)
            actions = exploration_policy_fn(q_values, total_t)
            next_states, rewards, dones, info = env.step(actions)

            results_buffer.update(info)
            memory_buffer.extend(
                zip(states, actions, rewards, next_states, dones))

            states_batch, action_batch, reward_batch, next_states_batch, \
                done_batch = memory_buffer.sample(batch_size)

            # compute target batch (y)
            batch_size = states_batch.shape[0]
            best_actions = np.argmax(
                estimator.predict(sess, next_states_batch), axis=1)

            q_values_next_target = estimator.target_predict(
                sess, next_states_batch)
            discount_factor_batch = np.invert(done_batch).astype(
                np.float32) * discount_factor
            targets_batch = reward_batch + discount_factor_batch * \
                q_values_next_target[np.arange(batch_size), best_actions]

            # update
            summaries, total_t, _ = estimator.update(
                sess, states_batch, action_batch, targets_batch)

            if total_t % update_target_every == 0:
                estimator.target_update(sess)

            if total_t % save_model_every == 0:
                saver.save(
                    sess,
                    os.path.join(checkpoint_path, 'model'),
                    total_t,
                    write_meta_graph=False)
                print("Save session, global_step: {}.".format(total_t))

                summary_writer.add_summary(summaries, total_t)
                results_buffer.record(summary_writer, total_t,
                                      time.time() - start)
                start = time.time()

            states = next_states

    except KeyboardInterrupt:
        print("\nKeyboard interrupt!")

    except Exception:
        traceback.print_exc()

    finally:
        saver.save(
            sess,
            os.path.join(checkpoint_path, 'model'),
            total_t,
            write_meta_graph=False)
        env.close()
