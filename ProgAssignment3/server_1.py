'''
This module defines the behaviour of server in your Chat Application
'''
import sys
import getopt
import socket
import util

class Server:
    '''
    This is the main Server Class. You will  write Server code inside this class.
    '''
    def __init__(self, dest, port, window):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(None)
        self.sock.bind((self.server_addr, self.server_port))

        self.clients = {}

    def start(self):
        '''
        Main loop.
        continue receiving messages from Clients and processing it.

        '''
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                if data:
                    msg_type, seqno, data, checksum = util.parse_packet(data.decode())
                    self.process_message(data, addr, seqno)
            except KeyboardInterrupt:
                break
            except:
                # If this somehow runs, it sends a err_unknown_message
                sender = None
                for key, value in self.clients.items():
                    if value == addr:
                        sender = key
                        break
                error_msg = f"disconnected: {sender} sent unknown command"
                print(error_msg)
                # Create message, then packet, then send through socket
                error_message = util.make_message('err_unknown_message', 2, error_msg)
                error_packet = util.make_packet('data', int(seqno), error_message)
                self.sock.sendto(error_packet.encode(), addr)

    
    def process_message(self, message, addr, seqno):
        parsed_message = message.split(' ', 1)
        msg_type = parsed_message[0]
        msg_remain = parsed_message[1]

        if msg_type == "join":
            # Add client and its address to the dictionary if possible
            join_message = msg_remain.split(' ', 1)
            msg_len = join_message[0]
            msg_data = join_message[1]
            if len(self.clients) == util.MAX_NUM_CLIENTS:
                # Create message, then packet, then send through socket
                reply_msg = util.make_message("err_server_full", 1, "err_server_full")
                reply_packet = util.make_packet("data", int(seqno), reply_msg)
                self.sock.sendto(reply_packet.encode(), addr)
            elif msg_data in self.clients:
                # Create message, then packet, then send through socket
                reply_msg = util.make_message("err_username_unavailable", 1, "err_username_unavailable")
                reply_packet = util.make_packet("data", int(seqno), reply_msg)
                self.sock.sendto(reply_packet.encode(), addr)
            else:
                self.clients[msg_data] = addr
                print(f"join: {msg_data}")
        elif msg_type == "request_users_list":
            # Locate sender using dictionary
            sender = None
            for key, value in self.clients.items():
                if value == addr:
                    sender = key
                    break
            print(f"request_users_list: {sender}")
            sorted_users = sorted(self.clients.keys())
            # Create list message, then packet, then send through socket
            reply_msg = util.make_message('response_users_list', 3, ' '.join(sorted_users))
            reply_packet = util.make_packet('data', int(seqno), reply_msg)
            self.sock.sendto(reply_packet.encode(), addr)
        elif msg_type == "send_message":
            send_message = msg_remain.split(' ', 1)
            msg_len = send_message[0]
            send_message = send_message[1].split(' ')
            user_count = int(send_message[0])
            user_list = send_message[1:user_count + 1]
            message = ' '.join(send_message[user_count + 1:])
            # Locate sender using dictionary
            sender = None
            for key, value in self.clients.items():
                if value == addr:
                    sender = key
                    break
            #Sending Message to each user in the send list
            for user in set(user_list):
                print(f"msg: {sender}")
                if user not in self.clients.keys():
                    print(f"msg: {sender} to non-existent user {user}")
                else:
                    # Create message, then packet, then send through socket
                    forward_message = util.make_message('forward_message', 4, f"{sender}: {message}")
                    forward_packet = util.make_packet('data', int(seqno), forward_message)
                    self.sock.sendto(forward_packet.encode(), self.clients[user])

        elif msg_type == "disconnect":
            # Remove by popping username off the dictionary
            disconnect_msg = msg_remain.split(' ', 1)
            msg_len = disconnect_msg[0]
            msg_data = disconnect_msg[1]
            self.clients.pop(msg_data)
            print(f"disconnected: {msg_data}")

        else:
            # Locate sender in dictionary
            sender = None
            for key, value in self.clients.items():
                if value == addr:
                    sender = key
                    break
            error_msg = f"disconnected: {sender} sent unknown command"
            print(error_msg)
            # Create err message, then packet, then send through socket
            error_message = util.make_message('err_unknown_message', 2, error_msg)
            error_packet = util.make_packet('data', int(seqno), error_message)
            self.sock.sendto(error_packet.encode(), addr)

# Do not change below part of code

if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our module completion
        '''
        print("Server")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW | --window=WINDOW The window size, default is 3")
        print("-h | --help Print this help")

    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "p:a:w", ["port=", "address=","window="])
    except getopt.GetoptError:
        helper()
        exit()

    PORT = 15000
    DEST = "localhost"
    WINDOW = 3

    for o, a in OPTS:
        if o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW = a

    SERVER = Server(DEST, PORT,WINDOW)
    try:
        SERVER.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
