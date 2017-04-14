from __future__ import print_function
import threading
import socket
import json
import struct
from base64 import b64encode
from hashlib import sha1

class WebSocketServer:
    """
    Basic implementation for web sockets. Usage:

    ws_server = WebSocketServer()
    ws_server.serve_forever(client_connection_callback, client_message_callback)

    ws_server.lock.acquire()
    for client in ws_server.clients:
        client.send(ws_server.encode_message("Hello World!"))
    ws_server.lock.release()

    def client_connection_callback(ws_server, socket):
        socket.send(ws_server.encode_message("Welcome!"))

    def client_message_callback(ws_server, socket, message):
        print(message)
    """

    MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    HANDSHAKE_STR = (
        b"HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: %s\r\n\r\n"
    )

    def __init__(self, port=8001):
        """
        Set up web socket server on specified port
        """

        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("", self.port))
        self.socket.listen(1)
        self.clients = []
        self.lock = threading.Lock()

    def serve_forever(self, client_connection_callback=None, client_message_callback=None):
        """
        Listen for web socket requests and spawn new thread for each client
        On connection, the thread will call client_connection_callback(WebSocketServer, socket)
        On receiving client messages, the thread will call client_message_callback(WebSocketServer, socket)
        """

        while True:
            client, _ = self.socket.accept()
            t = threading.Thread(target=self.handle_client, args=(client, client_connection_callback, client_message_callback))
            t.daemon = True
            t.start()

    def handle_client(self, client, client_connection_callback, client_message_callback):
        """
        Connect to client and listen for messages until connection is closed
        """

        # Handshake with client
        for line in client.recv(1024).splitlines():
            if line.startswith(b"Sec-WebSocket-Key"):
                client_key = line[line.index(b":")+1:].strip()
                break
        accept_key = b64encode(sha1(client_key + WebSocketServer.MAGIC).digest())
        client.send(WebSocketServer.HANDSHAKE_STR % accept_key)

        # Send client all keys
        if client_connection_callback is not None:
            client_connection_callback(self, client)

        # Add client to list
        self.lock.acquire()
        self.clients.append(client)
        self.lock.release()

        # Listen for messages
        while True:
            message = client.recv(1024)
            message = self.decode_message(message)
            if client_message_callback is not None:
                client_message_callback(self, client, message)
            if message is None:
                break

        # Close connection to client
        self.lock.acquire()
        self.clients.remove(client)
        self.lock.release()
        client.close()

    def encode_message(self, s):
        """
        Encode web socket message to send to client
        """

        if type(s) == bytes:
            payload = s
        elif type(s) == str:
            payload = s.encode("utf-8")
        else:
            payload = json.dumps(s).encode("utf-8")

        # Send entire message as one frame
        b1 = 0x80
        # Send text data
        b1 |= 0x01
        message = struct.pack("!B", b1)

        # Encode message length
        length = len(payload)
        if length < 126:
            b2 = length
            message += struct.pack("!B", b2)
        elif length < (2 ** 16) - 1:
            b2 = 126
            message += struct.pack("!BH", b2, length)
        else:
            b2 = 127
            message += struct.pack("!BQ", b2, length)

        # Append message
        message += payload

        return message

    def decode_message(self, s):
        """
        Decode web socket message from client
        """
        # Turn string values into opererable numeric byte values
        byte_array = [ord(character) for character in s.decode("utf-8")]
        if not byte_array:
            return None

        # TODO: check that op_code is correct
        op_code = byte_array[0] >> 4
        payload_length = byte_array[1] & 127

        # Extract masks
        idx_first_mask = 2
        if payload_length == 126:
            idx_first_mask = 4
        elif payload_length == 127:
            idx_first_mask = 10
        idx_first_data = idx_first_mask + 4
        masks = [m for m in byte_array[idx_first_mask:idx_first_data]]

        # Decode data
        decoded_chars = [chr(byte_array[j] ^ masks[i % 4]) for i, j in enumerate(range(idx_first_data, len(byte_array)))]

        return "".join(decoded_chars)
