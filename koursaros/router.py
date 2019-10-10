from .network import Network, Route, SocketType, FLASK_PORT
from flask import Flask, request, jsonify
from kctl.logger import set_logger
from .messages import Messages, MsgType
import json


class Router:
    """
    The router serves as an endpoint as a client. It receives
    requests from the client to send to the loop starting
    from a specific loop. It then redirects the network through it.
    """

    def __init__(self):
        # set logger
        self.logger = set_logger('router')
        self.logger.info('Initializing router')

        # set zeromq
        self.net = Network()
        self.net.build_socket(SocketType.PUB_BIND, Route.CTRL)
        self.net.build_socket(SocketType.PULL_BIND, Route.IN, name='ROUTER')

        # setup messages
        self.msgs = Messages()
        self.msg_count = 0

    def set_push_socket(self, service):
        self.net.build_socket(SocketType.PUSH_CONNECT, Route.OUT, name=service)

    def wait_for_first_service(self):
        # ask services for status
        self.net.send(Route.CTRL, 0, b'')

        while True:
            msg_id, msg = self.net.recv(Route.IN)

            if msg != b'':
                self.set_push_socket(msg.decode())
                break

    def send_msg(self, msg):
        self.msg_count += 1

        # use message count if no id is found in data
        msg_id = msg.pop('id') if 'id' in msg else self.msg_count
        msg = self.msgs.cast(msg, MsgType.JSON, MsgType.JSONBYTES)
        self.net.send(Route.OUT, msg_id, msg)

        # wait for response from service
        msg_id, msg = self.net.recv(Route.CTRL)
        res = json.loads(msg)

        res['id'] = msg_id
        return res

    def create_flask_app(self):
        app = Flask(__name__)
        router = self

        @app.route('/send')
        def receive():
            if Route.OUT not in self.net.sockets:
                router.wait_for_first_service()

            data = request.form if request.form else request.json
            res = router.send_msg(data)
            return jsonify(res)

        return app

    def run(self):
        app = self.create_flask_app()
        self.logger.info('Starting flask on port %s' % FLASK_PORT)
        app.run(port=FLASK_PORT, threaded=True, host='0.0.0.0')


if __name__ == "__main__":
    r = Router()
    r.run()
