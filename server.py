#!/usr/bin/env python
"""
server.py

Author: Toki Migimatsu
Created: April 2017
"""

from __future__ import print_function, division
import threading
from multiprocessing import Process
from argparse import ArgumentParser
import redis
import json
import time
import sys
import math
import os
import shutil

from WebSocketServer import WebSocketServer
from HTTPRequestHandler import makeHTTPRequestHandler

if sys.version.startswith("3"):
    from http.server import HTTPServer
else:
    from BaseHTTPServer import HTTPServer


class RedisMonitor:
    """
    Monitor Redis keys and send updates to all web socket clients.
    """

    def __init__(self, host="localhost", port=6379, db=0, refresh_rate=0.5, realtime=False):
        """
        If realtime is specified, RedisMonitor will enable notifications for all
        set events and subscribe to these notifications.
        """

        self.host = host
        self.port = port
        self.db = db
        self.refresh_rate = refresh_rate
        self.realtime = realtime

        self.redis_db = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
        self.message_last = {}

        if self.realtime:
            self.pubsub = self.redis_db.pubsub()
            self.lock = threading.Lock()
            self.message_buffer = []

            #  Need to perform the following command to enable keyevent notifications:
            #  config set notify-keyspace-events "$E"
            notify_keyspace_events = self.redis_db.config_get("notify-keyspace-events")["notify-keyspace-events"]
            if "$" not in notify_keyspace_events and "A" not in notify_keyspace_events:
                # Add string commands to notifications
                notify_keyspace_events += "$"
            if "E" not in notify_keyspace_events:
                # Add keyevent events to notifications
                notify_keyspace_events += "E"
            self.redis_db.config_set("notify-keyspace-events", notify_keyspace_events)

            self.pubsub.psubscribe("__keyevent@%s__:set" % self.db)

    def messenger(self, ws_server):
        """
        When realtime is set, this thread sends messages to all web socket
        clients every refresh_rate seconds.
        """

        while True:
            time.sleep(self.refresh_rate)

            self.lock.acquire()
            if not self.message_buffer:
                self.lock.release()
                continue

            keyvals = self.message_buffer
            self.message_buffer = []
            self.lock.release()

            ws_server.lock.acquire()
            for client in ws_server.clients:
                client.send(ws_server.encode_message(keyvals))
            ws_server.lock.release()

    def parse_val(self, key, skip_unchanged=True):
        """
        Get the value from Redis and parse if it's an array.
        If skip_unchanged = True, only returns values updated since the last call.
        """

        def isnumeric(s):
            """
            Helper function to test if string is a number
            """
            try:
                float(s)
                return True
            except ValueError:
                return False

        val = self.redis_db.get(key)

        # Skip if the value hasn't changed
        if skip_unchanged:
            if key in self.message_last and val == self.message_last[key]:
                return None
        self.message_last[key] = val

        try:
            # If the first element is a number, try converting all the elements to numbers
            if isnumeric(val.split(" ")[0]):
                # Parse matrix rows
                val = [[float(el) for el in row.split(" ") if el.strip()] for row in val.split(";")]
                val = [["NaN" if math.isnan(el) else el for el in row] for row in val]
        except:
            # Otherwise, leave it as a string
            pass

        return val

    def run_forever(self, ws_server):
        """
        Listen for redis keys (either realtime or every refresh_rate seconds)
        and send updated values to all web socket clients every refresh_rate seconds.
        """

        if not self.realtime:
            # Send messages to clients every refresh_rate seconds
            while True:
                time.sleep(self.refresh_rate)

                keyvals = []
                for key in self.redis_db.scan_iter():
                    if self.redis_db.type(key) != "string":
                        continue
                    val = self.parse_val(key)
                    if val is None:
                        continue
                    keyvals.append((key, val))

                if not keyvals:
                    continue

                ws_server.lock.acquire()
                for client in ws_server.clients:
                    client.send(ws_server.encode_message(keyvals))
                ws_server.lock.release()

        else:
            # Create thread to send messages to client with refresh rate
            messenger_thread = threading.Thread(target=self.messenger, args=(ws_server,))
            messenger_thread.daemon = True
            messenger_thread.start()

            # Listen for redis notifications
            for msg in self.pubsub.listen():
                if msg["pattern"] is None:
                    continue

                key = msg["data"]
                val = self.parse_val(key)
                if val is None:
                    continue

                self.lock.acquire()
                self.message_buffer.append((key, val))
                self.lock.release()

    def initialize_client(self, ws_server, client):
        """
        On first connection, send client all Redis keys.
        """

        keyvals = []

        self.message_last = {}
        for key in sorted(self.redis_db.scan_iter()):
            if self.redis_db.type(key) != "string":
                continue

            val = self.parse_val(key, skip_unchanged=False)
            if val is None:
                continue

            keyvals.append((key, val))

        client.send(ws_server.encode_message(keyvals))


def handle_get_request(request_handler, get_vars, **kwargs):
    """
    HTTPRequestHandler callback:

    Serve content inside WEB_DIRECTORY
    """
    WEB_DIRECTORY = "web"
    path_tokens = [token for token in request_handler.path.split("/") if token]

    # Default to index.html
    if not path_tokens or ".." in path_tokens:
        request_path = "index.html"
    else:
        request_path = os.path.join(*path_tokens)
    request_path = os.path.join(WEB_DIRECTORY, request_path)

    # Check if file exists
    if not os.path.isfile(request_path):
        request_handler.send_error(404, "File not found.")
        return

    # Insert ws_port into redis-web-gui.js
    if request_path == os.path.join(WEB_DIRECTORY, "js", "redis-web-gui.js"):
        with open(request_path) as f:
            html = f.read() % {"ws_port": kwargs["ws_port"]}
        request_handler.wfile.write(html.encode("utf-8"))
        return

    # Otherwise send file directly
    with open(request_path, "rb") as f:
        shutil.copyfileobj(f, request_handler.wfile)

def handle_post_request(request_handler, post_vars, **kwargs):
    """
    HTTPRequestHandler callback:

    Set POST variables as Redis keys
    """

    for key, val_str in post_vars.items():
        val_json = json.loads(val_str[0])
        if type(val_json) in (str, unicode):
            val = val_json
        else:
            val = "; ".join(" ".join(row) for row in val_json)
        print("%s: %s" % (key, val))
        kwargs["redis_db"].set(key, val)


if __name__ == "__main__":
    # Parse arguments
    parser = ArgumentParser(description=(
        "Monitor Redis keys in the browser."
    ))
    parser.add_argument("-hp", "--http_port", help="HTTP Port (default: 8000)", default=8000, type=int)
    parser.add_argument("-wp", "--ws_port", help="WebSocket port (default: 8001)", default=8001, type=int)
    parser.add_argument("-rh", "--redis_host", help="Redis hostname (default: localhost)", default="localhost")
    parser.add_argument("-rp", "--redis_port", help="Redis port (default: 6379)", default=6379, type=int)
    parser.add_argument("-rd", "--redis_db", help="Redis database number (default: 0)", default=0, type=int)
    parser.add_argument("-r", "--refresh_rate", help="Redis refresh rate in seconds (default: 0.5)", default=0.5, type=float)
    parser.add_argument("--realtime", action="store_true", help="Subscribe to realtime Redis SET pubsub notifications")
    args = parser.parse_args()

    # Create RedisMonitor, HTTPServer, and WebSocketServer
    print("Starting up server...\n")
    redis_monitor = RedisMonitor(host=args.redis_host, port=args.redis_port, db=args.redis_db, refresh_rate=args.refresh_rate, realtime=args.realtime)
    print("Connected to Redis database at %s:%d (db %d)" % (args.redis_host, args.redis_port, args.redis_db))
    get_post_args = {"ws_port": args.ws_port, "redis_db": redis_monitor.redis_db}
    http_server = HTTPServer(("", args.http_port), makeHTTPRequestHandler(handle_get_request, handle_post_request, get_post_args))
    ws_server = WebSocketServer(port=args.ws_port)

    # Start HTTPServer
    http_server_process = Process(target=http_server.serve_forever)
    http_server_process.start()
    print("Started HTTP server on port %d" % (args.http_port))

    # Start WebSocketServer
    ws_server_thread = threading.Thread(target=ws_server.serve_forever, args=(redis_monitor.initialize_client,))
    ws_server_thread.daemon = True
    ws_server_thread.start()
    print("Started WebSocket server on port %d\n" % (args.ws_port))

    # Start RedisMonitor
    print("Server ready. Listening for incoming connections.\n")
    redis_monitor.run_forever(ws_server)

    http_server_process.join()
