'''
This module defines the behaviour of server in your Chat Application
'''
import sys
import getopt
import socket
import util
import queue
import threading
import random
import time

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

        self.packet_queue = queue.Queue()
        self.acks_acked = {}
        self.message_store = {}

        self.client_states = {}

    def start(self):
        '''
        Main loop.
        continue receiving messages from Clients and processing it.

        '''
        try:
            t1 = threading.Thread(target=SERVER.packet_queuer)
            t2 = threading.Thread(target=SERVER.packet_hander)

            t1.start()
            t2.start()
        except KeyboardInterrupt:
            pass

    
    def process_message(self, message, addr, seqno, msg_type):
        seqno = int(seqno)

        # Track active session and seqno for retransmission
        if addr not in self.client_states.items():
            self.client_states[addr] = {'session_active': False, 'expected_seqno': seqno}

        client_state = self.client_states[addr]

        if msg_type == 'ack':
            self.acks_acked[addr] = True
            return
        elif msg_type == 'start':
            client_state['session_active'] = True
            client_state['expected_seqno'] = seqno + 1
            send_packet = util.make_packet('ack', seqno + 1, '')
            self.message_store[addr] = '' # Create new message
            self.sock.sendto(send_packet.encode(), addr)
            return
        elif msg_type == 'data':
            if not client_state['session_active'] or seqno != client_state['expected_seqno']:
                return
            client_state['expected_seqno'] += 1
            self.message_store[addr] += message # Rebuild the chunks
            send_packet = util.make_packet('ack', seqno + 1, '')
            self.sock.sendto(send_packet.encode(), addr)
            return
        elif msg_type == 'end':
            if not client_state['session_active'] or seqno != client_state['expected_seqno']:
                return  # Ignore the packet or send an error packet back
            client_state['session_active'] = False
            send_packet = util.make_packet('ack', seqno + 1, '')
            self.sock.sendto(send_packet.encode(), addr)

        parsed_message = self.message_store[addr].split(' ', 1)
        msg_type = parsed_message[0]

        if msg_type == "join":
            msg_remain = parsed_message[1]
            join_message = msg_remain.split(' ', 1)
            msg_len = join_message[0]
            msg_data = join_message[1]
            t1 = threading.Thread(target=self.handle_join, args=(msg_data, addr,), daemon=True)
            t1.start()
        elif msg_type == "request_users_list":
            t1 = threading.Thread(target=self.handle_list, args=(addr,), daemon=True)
            t1.start()
        elif msg_type == "send_message":
            msg_remain = parsed_message[1]
            send_message = msg_remain.split(' ', 1)
            msg_len = send_message[0]
            send_message = send_message[1].split(' ')
            user_count = int(send_message[0])
            user_list = send_message[1:user_count + 1]
            message = ' '.join(send_message[user_count + 1:])
            # Finder sender from dictionary
            sender = None
            for key, value in self.clients.items():
                if value == addr:
                    sender = key
                    break
            #Sending Message
            for user in set(user_list):
                print(f"msg: {sender}")
                if user not in self.clients.keys():
                    print(f"msg: {sender} to non-existent user {user}")
                else:
                    forward_message = util.make_message('forward_message', 4, f"{sender}: {message}")
                    t1 = threading.Thread(target=self.packet_sender, args=(forward_message, self.clients[user],), daemon=True)
                    t1.start()

        # Disconnect handling
        elif msg_type == "disconnect":
            msg_remain = parsed_message[1]
            disconnect_msg = msg_remain.split(' ', 1)
            msg_len = disconnect_msg[0]
            msg_data = disconnect_msg[1]
            self.clients.pop(msg_data)
            print(f"disconnected: {msg_data}")

        # Error occurs or unknown thing occurs
        else:
            sender = None
            for key, value in self.clients.items():
                if value == addr:
                    sender = key
                    break
            error_msg = f"disconnected: {sender} sent unknown command"
            print(error_msg)
            error_message = util.make_message('err_unknown_message', 2, error_msg)
            error_packet = util.make_packet('data', int(seqno), error_message)
            self.sock.sendto(error_packet.encode(), addr)
    
    # Queues packets that are received for processing
    def packet_queuer(self):
        while True:
            packet, address = self.sock.recvfrom(4000)
            self.packet_queue.put((packet, address))

    # Handles the processing of packets
    def packet_hander(self):
        while True:
            while not self.packet_queue.empty():
                packet, address = self.packet_queue.get()
                msg_type, seqno, data, checksum = util.parse_packet(packet.decode())
                self.process_message(data, address, seqno, msg_type)

    # Handles adding a new client to the dictionary or not if its full or name is used
    def handle_join(self, name, addr):
        if len(self.clients) == util.MAX_NUM_CLIENTS:
            reply_msg = util.make_message("err_server_full", 1, "err_server_full")
            self.packet_sender(reply_msg, addr)
        elif name in self.clients:
            reply_msg = util.make_message("err_username_unavailable", 1, "err_username_unavailable")
            self.packet_sender(reply_msg, addr)
        else:
            self.clients[name] = addr
            print(f"join: {name}")

    # Handles the user_list request
    def handle_list(self, addr):
        sender = None
        for key, value in self.clients.items():
            if value == addr:
                sender = key
                break
        print(f"request_users_list: {sender}")
        sorted_users = sorted(self.clients.keys())
        reply_msg = util.make_message('response_users_list', 3, ' '.join(sorted_users))
        self.packet_sender(reply_msg, addr)

    def packet_sender(self, message, addr):
        seqno = random.randint(1000, 9900)
        # Start packet
        start_packet = util.make_packet('start', seqno, '')
        self.sock.sendto(start_packet.encode(), addr)

        self.acks_acked[addr] = False
        start_time = time.time()
        # Ensure start packet is sent and received
        while not self.acks_acked[addr]:
           if time.time() - start_time >= util.TIME_OUT:
                self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))
                start_time = time.time()
        self.acks_acked[addr] = False

        # Split into chunks
        chunks = [message[i: i + util.CHUNK_SIZE] for i in range(0, len(message), util.CHUNK_SIZE)]

        counter = 1
        # Send each chunk
        for chunk in chunks:
            counter += 1
            seqno += 1
            send_packet = util.make_packet('data', seqno, chunk)
            self.sock.sendto(send_packet.encode(), addr)

            # Ensure each chunk packet is sent and received
            while not self.acks_acked[addr]:
                if time.time() - start_time >= util.TIME_OUT:
                    self.sock.sendto(send_packet.encode(), (self.server_addr, self.server_port))
                    start_time = time.time()
            self.acks_acked[addr] = False

        seqno += 1

        # End packet
        end_packet = util.make_packet('end', seqno, '')
        self.sock.sendto(end_packet.encode(), addr)
        # Ensure end packet is sent and received
        while not self.acks_acked[addr]:
            if time.time() - start_time >= util.TIME_OUT:
                self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))
                start_time = time.time()
    

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
