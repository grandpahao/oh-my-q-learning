import gym
import zmq
import click
import msgpack
import msgpack_numpy
msgpack_numpy.patch()


class SubAgent(object):
    def __init__(self, game_name, identity, url):
        self.env = gym.make(game_name)
        self.identity = 'SubAgent-{}'.format(identity)
        self.url = url

        self.action_n = self.env.action_space.n
        self.allowed_actions = list(range(self.action_n))

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.identity = self.identity.encode('utf-8')
        socket.connect(self.url)

        # Reset env
        print('subagent {} start!'.format(self.identity))
        socket.send(
            msgpack.dumps(('ready', self.action_n,
                           self.env.observation_space.shape)))

        while True:
            action = socket.recv()
            if action == b'reset':
                game_reward = 0
                state = self.env.reset()
                socket.send(msgpack.dumps(state))
                continue

            if action == b'close':
                socket.close()
                context.term()
                break

            action = msgpack.loads(action)
            assert action in self.allowed_actions
            next_state, reward, done, _ = self.env.step(action)
            game_reward += reward
            info = None
            if done:
                next_state = self.env.reset()
                info = game_reward
                game_reward = 0

            socket.send(msgpack.dumps((next_state, reward, done, info)))


@click.command()
@click.option('--game_name')
@click.option('--identity')
def main(game_name, identity):
    s = SubAgent(game_name, identity,
                 'ipc://./.ipc/{}/Agent.ipc'.format(game_name))
    s.run()


if __name__ == '__main__':
    main()
