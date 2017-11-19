import cv2
import numpy as np
from collections import deque
from ale_python_interface import ALEInterface


class Wrapper(object):
    skip_skip_obs_buffer = deque(maxlen=2)
    lives = 0
    real_done = True

    def __init__(self, env, game_name, skip=4, stack=4):
        self.env = env
        self.game_name = game_name
        self.skip = skip
        self.stack = stack

        self.obs_buffer = deque(maxlen=stack)
        self.action_set = env.getMinimalActionSet()
        self.action_n = len(self.action_set)

    def step(self, a):
        total_reward = 0.0
        done = None
        action = self.action_set[a]
        for _ in range(self.skip):
            # Rewards
            r = self.env.act(action)
            total_reward += r

            # Obs(state)
            obs = Wrapper.process(self.env.getScreenGrayscale())
            self.skip_obs_buffer.append(obs)

            # Done
            lives = self.env.lives()
            done = lives < self.lives
            self.lives = lives
            self.real_done = self.env.game_over()

            if done:
                break
        max_frame = np.max(np.stack(self.skip_obs_buffer), axis=0)

        self.obs_buffer.append(max_frame)
        return np.concatenate(
            self.obs_buffer, axis=2), total_reward, done, None

    def reset(self):
        self.skip_obs_buffer.clear()
        if self.real_done:
            self.env.reset_game()
            obs = Wrapper.process(self.env.getScreenGrayscale())
            self.skip_obs_buffer.append(obs)
        else:
            obs, _, _ = self.step(0)

        for _ in range(self.stack):
            self.obs_buffer.append(obs)
        return np.concatenate(self.obs_buffer, axis=2)

    @staticmethod
    def process(frame):
        frame = cv2.resize(frame, (84, 84), interpolation=cv2.INTER_AREA)
        return frame[:, :, np.newaxis]


def wrap_env(game_name, skip=4, stack=4):
    env = ALEInterface()
    name = './games/' + game_name + '.bin'
    env.loadROM(name.encode('utf-8'))
    env = Wrapper(env, game_name, skip=skip, stack=4)
    return env
