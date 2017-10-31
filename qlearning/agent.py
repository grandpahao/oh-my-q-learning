import zmq
import pickle
import msgpack
import numpy as np
import msgpack_numpy
from lib.util import str_reward
from threading import Thread
from multiprocessing import Process
from lib.atari_wrapper import make_env

msgpack_numpy.patch()


class Agent(Thread):
    def __init__(self, game_name, url, i):
        super(Agent, self).__init__()
        self.env = make_env(game_name)
        self.rewards_stats = []
        self.url = url
        self.identity = ('Agent-%d' % i).encode('utf-8')

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.identity = self.identity
        socket.connect(self.url)

        state = self.env.reset()
        socket.send(msgpack.dumps(('reset', state)))
        episode_reward = 0
        episode_length = 0
        while True:
            reply = socket.recv()
            action = msgpack.loads(reply)
            next_state, reward, done, _ = self.env.step(action)
            episode_reward += reward
            episode_length += 1
            socket.send(
                msgpack.dumps(('step', state, action, np.sign(reward),
                               next_state, done)))
            state = next_state
            if done:
                reply = socket.recv()
                assert reply == b'reset'
                self.rewards_stats.append(episode_reward)
                print('\n'.join([
                    '\n',
                    self.identity.decode('utf-8'), 'episode length: {}'.format(
                        episode_length),
                    str_reward(self.rewards_stats, 50)
                ]))
                if len(self.rewards_stats) % 100 == 0:
                    f = open('./tmp/' + self.identity.decode('utf-8') + '.pkl',
                             'wb')
                    pickle.dump(self.rewards_stats, f)
                    f.close()
                episode_reward = 0
                episode_length = 0
                state = self.env.reset()
                socket.send(msgpack.dumps(('reset', state)))
