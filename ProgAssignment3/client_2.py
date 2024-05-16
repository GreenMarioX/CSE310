'''
This module defines the behaviour of a client in your Chat Application
'''
import sys
import getopt
import socket
import random
from threading import Thread
import os
import util
import time
'''
Write your code inside this class. 
In the start() function, you will read user-input and act accordingly.
receive_handler() function is running another thread and you have to listen 
for incoming messages in this function.
'''

class Client:
    '''
    This is the main Client Class. 
    '''
    def __init__(self, username, dest, port, window_size):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(None)
        self.sock.bind(('', random.randint(10000, 40000)))
        self.name = username

        self.seqno = 0
        self.running = True

        self.ack_acked = False

    def start(self):
        '''
        Main Loop is here
        Start by sending the server a JOIN message. 
        Use make_message() and make_util() functions from util.py to make your first join packet
        Waits for userinput and then process it
        '''
        self.packet_sender('join')

        try:
            while self.running:
                message = input()
                # Determine the route to take based on input
                if message.startswith("msg") or message == 'list':
                    self.packet_sender(message)
                elif message == 'quit':
                    self.packet_sender(message)
                    self.running = False
                elif message == "help":
                    self.print_help()
                elif self.running == False:
                    break
                else:
                    print("incorrect userinput format")

        finally:
            self.sock.close()
            

    def receive_handler(self):
        '''
        Waits for a message from server and process it accordingly
        '''
        rebuilt_message = ''
        while self.running:
            try:
                receive_packet, address = self.sock.recvfrom(4000)
                msg_type, seqno, data, checksum = util.parse_packet(receive_packet.decode())
                if msg_type == 'ack': # if its just an ack packet, we don't need to do anything
                    self.ack_acked = True
                    continue
                elif msg_type == 'start':
                    rebuilt_message = '' # New message means new message to rebuild
                    send_packet = util.make_packet('ack', int(seqno) + 1, '')
                    self.sock.sendto(send_packet.encode(), address)
                    continue
                elif msg_type == 'data': 
                    rebuilt_message += data # Assemble the chunks
                    send_packet = util.make_packet('ack', int(seqno) + 1, '')
                    self.sock.sendto(send_packet.encode(), address)
                    continue
                elif msg_type == 'end': # We can move on to extraction of data
                    send_packet = util.make_packet('ack', int(seqno) + 1, '')
                    self.sock.sendto(send_packet.encode(), address)

                # Same as Part I, we want to extract the important stuff
                extract_msg = rebuilt_message.split(' ', 1)
                extract_msg_type = extract_msg[0]
                if extract_msg_type == 'response_users_list':
                    extract_msg = extract_msg[1].split(' ', 1)
                    to_print = extract_msg[1]
                    print(f"list: {to_print}")
                elif extract_msg_type == 'forward_message':
                    extract_msg = extract_msg[1].split(' ', 1)
                    to_print = extract_msg[1]
                    print(f"msg: {to_print}")
                elif extract_msg_type == 'err_unknown_message':
                    print(f"disconnected: server received an unknown command")
                    self.running = False
                    quit_message = util.make_message("disconnect", 1, self.name)
                    quit_packet = util.make_packet('data', self.seqno, quit_message)
                    self.sock.sendto(quit_packet.encode(), (self.server_addr, self.server_port))
                    self.sock.close()
                    break
                elif extract_msg_type == 'err_server_full':
                    print(f"disconnected: server full")
                    self.running = False
                    self.sock.close()
                    break
                elif extract_msg_type == 'err_username_unavailable':
                    print(f"disconnected: username not available")
                    self.running = False
                    self.sock.close()
                    break
            except socket.timeout:
                continue
            except Exception as e:
                break

    def print_help(self):
        print("Available commands:")
        print("  msg <number_of_users> <username1> <username2> ... <message>")
        print("  list")
        print("  help")
        print("  quit")

    def packet_sender(self, action):
        seqno = random.randint(1000, 9900)
        # Start Packet
        start_packet = util.make_packet('start', seqno, '')
        self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        # Ensure start packet is send and received.
        start_time = time.time()
        while not self.ack_acked:
            if time.time() - start_time >= util.TIME_OUT:
                self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))
        self.ack_acked = False

        # Create the message payload we want to send
        send_message = ''
        if action == "join":
            send_message = util.make_message('join', 1, self.name)
        elif action == "list":
            send_message = util.make_message("request_users_list", 2)
        elif action == "quit":
            send_message = util.make_message("disconnect", 1, self.name)
        elif action.startswith("msg"):
            message_split = action.split()
            if len(message_split) > 1:
                message = ' '.join(message_split[1:])
            send_message = util.make_message('send_message', 4, message)

        # Splitting of message into chunks
        chunks = [send_message[i: i + util.CHUNK_SIZE] for i in range(0, len(send_message), util.CHUNK_SIZE)]

        counter = 1
        # Send each chunk
        for chunk in chunks:
            counter += 1
            seqno += 1
            send_packet = util.make_packet("data", seqno, chunk)
            self.sock.sendto(send_packet.encode(), (self.server_addr, self.server_port))

            start_time = time.time()
            # Ensure each chunk is sent and received
            while not self.ack_acked:
                if time.time() - start_time >= util.TIME_OUT:
                    self.sock.sendto(send_packet.encode(), (self.server_addr, self.server_port))
                    start_time = time.time()
            self.ack_acked = False
        
        # 'end' packet transmission
        seqno += 1
        end_packet = util.make_packet('end', seqno, '')
        self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))
        start_time = time.time()
        # Ensure end packet is sent and received
        while not self.ack_acked:
            if time.time() - start_time >= util.TIME_OUT:
                    self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))
                    start_time = time.time()
        self.ack_acked = False

        if action == "quit":
            print("quitting".strip())


# Do not change below part of code
if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our Client module completion
        '''
        print("Client")
        print("-u username | --user=username The username of Client")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW_SIZE | --window=WINDOW_SIZE The window_size, defaults to 3")
        print("-h | --help Print this help")
    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "u:p:a:w", ["user=", "port=", "address=","window="])
    except getopt.error:
        helper()
        exit(1)

    PORT = 15000
    DEST = "localhost"
    USER_NAME = None
    WINDOW_SIZE = 3
    for o, a in OPTS:
        if o in ("-u", "--user="):
            USER_NAME = a
        elif o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW_SIZE = a

    if USER_NAME is None:
        print("Missing Username.")
        helper()
        exit(1)

    S = Client(USER_NAME, DEST, PORT, WINDOW_SIZE)
    try:
        # Start receiving Messages
        T = Thread(target=S.receive_handler)
        T.daemon = True
        T.start()
        # Start Client
        S.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
