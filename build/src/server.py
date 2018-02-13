#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import socket
import traceback
from functools import wraps

import eventlet
eventlet.monkey_patch(thread=True, time=True)
from builtins import bytes
import click
import msgpack
import flask
from flask import (Flask, render_template, make_response, copy_current_request_context,
                   jsonify, request, Response)
from flask_socketio import SocketIO
from bowtie._component import COMPONENT_REGISTRY


# python 2 compatibility
try:
    FileNotFoundError
except NameError:
    FileNotFoundError = OSError


class GetterNotDefined(AttributeError):
    pass


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'username' and password == 'password'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# import the user created module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import kick

app = Flask(__name__)
app.debug = True
socketio = SocketIO(app, binary=True, path='' + 'socket.io')
# not sure if this is secure or how much it matters
app.secret_key = os.urandom(256)

def context(func):
    def foo():
        with app.app_context():
            func()
    return foo


class Scheduler(object):

    def __init__(self, seconds, func):
        self.seconds = seconds
        self.func = func
        self.thread = None

    def start(self):
        self.thread = eventlet.spawn(self.run)

    def run(self):
        ret = eventlet.spawn(context(self.func))
        eventlet.sleep(self.seconds)
        try:
            ret.wait()
        except:
            traceback.print_exc()
        self.thread = eventlet.spawn(self.run)

    def stop(self):
        if self.thread:
            self.thread.cancel()


@app.route('/')
def index():
    return render_template('index.html')




@app.route('/static/bundle.js')
def getbundle():
    basedir = os.path.dirname(os.path.realpath(__file__))
    bundle_path = basedir + '/static/bundle.js'
    bundle_path_gz = bundle_path + '.gz'

    try:
        if os.path.getmtime(bundle_path) > os.path.getmtime(bundle_path_gz):
            return open(bundle_path, 'r').read()
        else:
            bundle = open(bundle_path_gz, 'rb').read()
            response = flask.make_response(bundle)
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.data)
            return response
    except FileNotFoundError:
        if os.path.isfile(bundle_path_gz):
            bundle = open(bundle_path_gz, 'rb').read()
            response = flask.make_response(bundle)
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.data)
            return response
        else:
            return open(bundle_path, 'r').read()


@socketio.on('INITIALIZE')
def _():
    foo = copy_current_request_context(kick.init)
    eventlet.spawn(foo)






@socketio.on('3#change')
def _(*args):
    def wrapuser():
        uniq_events = set()
        uniq_events.update([('3#change', 3, 'get')])
        uniq_events.update([('3#change', 3, 'get'), ('5#relayout', 5, 'get')])
        uniq_events.remove(('3#change', 3, 'get'))
        event_data = {}
        for ev in uniq_events:
            comp = COMPONENT_REGISTRY[ev[1]]
            if ev[2] is None:
                ename = ev[0]
                raise GetterNotDefined('{ctype} has no getter associated with event "on_{ename}"'
                                       .format(ctype=type(comp), ename=ename[ename.find('#') + 1:]))
            getter = getattr(comp, ev[2])
            event_data[ev[0]] = getter()

        # if there is no getter, then there is no data to unpack
        # if there is a getter, then we need to unpack the data sent
        event_data['3#change'] = COMPONENT_REGISTRY[3]._get(
            msgpack.unpackb(bytes(args[0]['data']), encoding='utf8')
        )

        # gather the remaining data from the other events through their getter methods
        user_args = []
        user_args.append(event_data['3#change'])

        # finally call the user method
        kick.update_pledged(*user_args)
        user_args = []
        user_args.append(event_data['3#change'])
        user_args.append(event_data['5#relayout'])

        # finally call the user method
        kick.update_counts(*user_args)

    foo = copy_current_request_context(wrapuser)
    eventlet.spawn(foo)

@socketio.on('5#relayout')
def _(*args):
    def wrapuser():
        uniq_events = set()
        uniq_events.update([('3#change', 3, 'get'), ('5#relayout', 5, 'get')])
        uniq_events.remove(('5#relayout', 5, 'get'))
        event_data = {}
        for ev in uniq_events:
            comp = COMPONENT_REGISTRY[ev[1]]
            if ev[2] is None:
                ename = ev[0]
                raise GetterNotDefined('{ctype} has no getter associated with event "on_{ename}"'
                                       .format(ctype=type(comp), ename=ename[ename.find('#') + 1:]))
            getter = getattr(comp, ev[2])
            event_data[ev[0]] = getter()

        # if there is no getter, then there is no data to unpack
        # if there is a getter, then we need to unpack the data sent
        event_data['5#relayout'] = COMPONENT_REGISTRY[5]._get(
            msgpack.unpackb(bytes(args[0]['data']), encoding='utf8')
        )

        # gather the remaining data from the other events through their getter methods
        user_args = []
        user_args.append(event_data['3#change'])
        user_args.append(event_data['5#relayout'])

        # finally call the user method
        kick.update_counts(*user_args)

    foo = copy_current_request_context(wrapuser)
    eventlet.spawn(foo)


@click.command()
@click.option('--host', '-h', default='0.0.0.0', help='Host IP')
@click.option('--port', '-p', default=9991, help='port number')
def main(host, port):
    scheduled = not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    if scheduled:
        scheds = []

        for sched in scheds:
            sched.start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    if result == 0:
        raise Exception('Port {} is unavailable on host {}, aborting.'.format(port, host))
    socketio.run(app, host=host, port=port)
    if scheduled:
        for sched in scheds:
            sched.stop()

if __name__ == '__main__':
    main()