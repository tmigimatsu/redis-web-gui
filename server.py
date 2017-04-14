#!/usr/bin/env python

from __future__ import print_function, division
import threading
from multiprocessing import Process
from argparse import ArgumentParser
import redis
import json
import time
import sys
if sys.version.startswith("3"):
    from http.server import BaseHTTPRequestHandler, HTTPServer
else:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from WebSocketServer import WebSocketServer

def isnumeric(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def makeHTTPRequestHandler(ws_port, redis_db):
    """
    Factory method to create HTTPRequestHandler class with ws_port, redis_db
    """

    class HTTPRequestHandler(BaseHTTPRequestHandler):

        def __init__(self, request, client_address, server):
            self.redis_db = redis_db
            BaseHTTPRequestHandler.__init__(self, request, client_address, server)

        def set_headers(self):
            """
            Return OK message
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

        def do_GET(self):
            """
            Handle GET request
            """
            self.set_headers()

            # Insert ws_port into html and return
            with open("index.html") as f:
                html = f.read() % {"ws_port": ws_port}
                self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            """
            Handle POST request
            """
            import cgi

            self.set_headers()

            # Parse post content
            content_type, parse_dict = cgi.parse_header(self.headers["Content-Type"])
            if content_type == "multipart/form-data":
                post_vars = cgi.parse_multipart(self.rfile, parse_dict)
            elif content_type == "application/x-www-form-urlencoded":
                content_length = int(self.headers["Content-Length"])
                post_vars = cgi.parse_qs(self.rfile.read(content_length), keep_blank_values=1)
            else:
                post_vars = {}

            # Set Redis keys
            for key, val in post_vars.items():
                val = " ".join(json.loads(val[0]))
                print("%s: %s" % (key, val))
                self.redis_db.set(key, val)

    return HTTPRequestHandler

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
                for key in self.redis_db.keys():
                    if self.redis_db.type(key) != "string":
                        continue
                    val = self.redis_db.get(key)
                    if key in self.message_last and val == self.message_last[key]:
                        continue
                    self.message_last[key] = val

                    if isnumeric(val.split(" ")[0]):
                        val = [float(el) for el in val.split(" ") if el.strip()]

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
                val = self.redis_db.get(key)
                if self.redis_db.type(key) != "string":
                    continue
                if key in self.message_last and val == self.message_last[key]:
                    continue
                self.message_last[key] = val

                if isnumeric(val.split(" ")[0]):
                    val = [el for el in val.split(" ") if el.strip()]

                self.lock.acquire()
                self.message_buffer.append((key, val))
                self.lock.release()

    def initialize_client(self, ws_server, client):
        """
        On first connection, send client all Redis keys.
        """

        keyvals = []

        for key in sorted(self.redis_db.keys()):
            if self.redis_db.type(key) != "string":
                continue
            val = self.redis_db.get(key)
            if isnumeric(val.split(" ")[0]):
                val = [el for el in val.split(" ") if el.strip()]

            keyvals.append((key, val))

        client.send(ws_server.encode_message(keyvals))



if __name__ == "__main__":
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
    redis_monitor = RedisMonitor(host=args.redis_host, port=args.redis_port, db=args.redis_db, refresh_rate=args.refresh_rate, realtime=args.realtime)
    print("Connected to Redis database at %s:%d (db %d)" % (args.redis_host, args.redis_port, args.redis_db))
    http_server = HTTPServer(("", args.http_port), makeHTTPRequestHandler(args.ws_port, redis_monitor.redis_db))
    ws_server = WebSocketServer()

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
    redis_monitor.run_forever(ws_server)

    http_server_process.join()
