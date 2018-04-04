import os
import time
import pickle
import numpy as np
from util import Memory
from collections import defaultdict


class ResultsBuffer(object):
    def __init__(self, rewards_history=[]):
        self.buffer = defaultdict(list)

        assert isinstance(rewards_history, list)
        self.rewards_history = rewards_history

    def update_infos(self, info, total_t):
        for key in info:
            msg = info[key]
            self.buffer['reward'].append(msg[b'reward'])
            self.buffer['length'].append(msg[b'length'])
            if b'real_reward' in msg:
                self.buffer['real_reward'].append(msg[b'real_reward'])
                self.buffer['real_length'].append(msg[b'real_length'])
                self.rewards_history.append(
                    [total_t, key, msg[b'real_reward']])

    def update_summaries(self, summaries, total_t):
        for k in summaries:
            self.buffer[k].append(summaries[k])

    def add_summary(self, summary_writer, total_t, time):
        s = {'time': time}
        for key in self.buffer:
            if self.buffer[key]:
                s[key] = np.mean(self.buffer[key])
                self.buffer[key].clear()
        for key in s:
            summary_writer.add_scalar(key, s[key], total_t)


def dqn(env,
        basename,
        estimator,
        batch_size,
        summary_writer,
        checkpoint_path,
        exploration_policy_fn,
        discount_factor=0.99,
        update_target_every=1,
        learning_starts=100,
        memory_size=100000,
        num_iterations=500000,
        update_summaries_every=1000,
        save_model_every=10000):

    estimator.restore(checkpoint_path)

    rewards_history = []
    pkl_path = 'train_log/{}/rewards.pkl'.format(basename)
    if os.path.exists(pkl_path):
        with open(pkl_path, 'rb') as f:
            rewards_history = pickle.load(f)

    total_t = estimator.get_global_step()

    memory_buffer = Memory(memory_size)
    results_buffer = ResultsBuffer(rewards_history)

    try:
        states = env.reset()
        for i in range(learning_starts):
            q_values = estimator.predict(states)
            actions = exploration_policy_fn(q_values, total_t)
            next_states, rewards, dones, _ = env.step(actions)

            memory_buffer.extend(zip(states, actions, rewards, next_states, dones))
            states = next_states

        states = env.reset()
        start = time.time()
        for i in range(num_iterations):
            q_values = estimator.predict(states)
            actions = exploration_policy_fn(q_values, total_t)
            next_states, rewards, dones, info = env.step(actions)

            results_buffer.update_infos(info, total_t)
            memory_buffer.extend(zip(states, actions, rewards, next_states, dones))

            # update
            total_t, summaries = estimator.update(discount_factor, *memory_buffer.sample(batch_size))
            results_buffer.update_summaries(summaries, total_t)

            if total_t % update_target_every == 0:
                estimator.target_update()
                summaries = estimator.alpha_update(discount_factor, *memory_buffer.sample(batch_size * 10))
                results_buffer.update_summaries(summaries, total_t)

            if total_t % update_summaries_every == 0:
                t = time.time() - start
                print("global_step: {}, delta_time: {}.".format(total_t, t))
                results_buffer.add_summary(summary_writer, total_t, t)
                start = time.time()

            if total_t % save_model_every == 0:
                estimator.save(checkpoint_path)
                print("save model...")

            states = next_states

    except Exception as e:
        raise e
    finally:
        estimator.save(checkpoint_path)

        with open(pkl_path, 'wb') as f:
            pickle.dump(results_buffer.rewards_history, f)
