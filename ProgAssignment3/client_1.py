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

    def start(self):
        '''
        Main Loop is here
        Start by sending the server a JOIN message. 
        Use make_message() and make_util() functions from util.py to make your first join packet
        Waits for userinput and then process it
        '''
        join_message = util.make_message('join', 1, self.name)
        join_packet = util.make_packet('data', self.seqno, join_message)
        self.sock.sendto(join_packet.encode(), (self.server_addr, self.server_port))

        try:
            while self.running:
                message = input()
                # determine which action to take based on user input
                if message.startswith("msg"):
                    message_split = message.split()
                    if len(message_split) > 1:
                        message = ' '.join(message_split[1:])
                    # Create message, then packet, then send through socket
                    message_message = util.make_message('send_message', 4, message)
                    message_packet = util.make_packet('data', self.seqno, message_message)
                    self.sock.sendto(message_packet.encode(), (self.server_addr, self.server_port))
                elif message == "list": 
                    # Create message, then packet, then send through socket
                    list_message = util.make_message("request_users_list", 2)
                    list_packet = util.make_packet('data', self.seqno, list_message)
                    self.sock.sendto(list_packet.encode(), (self.server_addr, self.server_port))
                elif message == "help":
                    self.print_help()
                elif message == "quit": # Quit Handler
                    print("quitting")
                    self.running = False
                    # Create message, then packet, then send through socket
                    quit_message = util.make_message("disconnect", 1, self.name)
                    quit_packet = util.make_packet('data', self.seqno, quit_message)
                    self.sock.sendto(quit_packet.encode(), (self.server_addr, self.server_port))
                    self.sock.close()
                    break
                else:
                    print("incorrect userinput format")
                    #error_message = util.make_message(message, 2)
                    #error_packet = util.make_packet('data', self.seqno, error_message)
                    #self.sock.sendto(error_packet.encode(), (self.server_addr, self.server_port))

        finally:
            self.sock.close()
            

    def receive_handler(self):
        '''
        Waits for a message from server and process it accordingly
        '''
        while self.running:
            try:
                data, _ = self.sock.recvfrom(1024)
                msg_type, seqno, data, checksum = util.parse_packet(data.decode())

                extract_msg = data.split(' ', 1)  # split into msg_type and the printed content
                extract_msg_type = extract_msg[0]
                if extract_msg_type == 'response_users_list':
                    # Format the message and print to stdout
                    extract_msg = extract_msg[1].split(' ', 1)
                    to_print = extract_msg[1]
                    print(f"list: {to_print}")
                elif extract_msg_type == 'forward_message':
                    # Format the message and print to stdout
                    extract_msg = extract_msg[1].split(' ', 1)
                    to_print = extract_msg[1]
                    print(f"msg: {to_print}")
                elif extract_msg_type == 'err_unknown_message':
                    # Quit uopn err_unknown_message
                    print(f"disconnected: server received an unknown command")
                    self.running = False
                    quit_message = util.make_message("disconnect", 1, self.name)
                    quit_packet = util.make_packet('data', self.seqno, quit_message)
                    self.sock.sendto(quit_packet.encode(), (self.server_addr, self.server_port))
                    self.sock.close()
                    break
                elif extract_msg_type == "err_server_full":
                    # Handle full server
                    print(f"disconnected: server full")
                    self.running = False
                    self.sock.close()
                    break
                elif extract_msg_type == "err_username_unavailable":
                    # Handle unavailable username
                    print(f"disconnected: username not available")
                    self.running = False
                    self.sock.close()
                    break
            except socket.timeout:
                continue
            except Exception as e:
                break

    # Helper function to print commands for help
    def print_help(self):
        print("Available commands:")
        print("  msg <number_of_users> <username1> <username2> ... <message>")
        print("  list")
        print("  help")
        print("  quit")

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
