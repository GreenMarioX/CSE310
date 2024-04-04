import dpkt
import sys
from dpkt.utils import inet_to_str


# Reads a file from console and then opens the pcap file with dpkt
def init_pcap_bytes():
    file_name = sys.argv[1]
    f = open(file_name, 'rb')
    pcap_bytes = dpkt.pcap.Reader(f)
    return pcap_bytes


# Returns a set of flows for analysis
def flow_info(pcap):
    flows = {}
    for timestamp, buf in pcap:
        try:
            # Unpack ethernet frame
            eth = dpkt.ethernet.Ethernet(buf)

            # Make sure the Ethernet frame contains an IP packet and TCP packet
            if not isinstance(eth.data, dpkt.ip.IP):
                continue
            ip = eth.data
            if not isinstance(ip.data, dpkt.tcp.TCP):
                continue
            tcp = ip.data

            current_pkt = {
                'syn': (eth.ip.data.flags & dpkt.tcp.TH_SYN),
                'ack': (eth.ip.data.flags & dpkt.tcp.TH_ACK),
                'fin': (eth.ip.data.flags & dpkt.tcp.TH_FIN),
                'src': inet_to_str(ip.src),
                'dst': inet_to_str(ip.dst),
                'timestamp': timestamp,
                'tcp': eth.ip.data,
            }

            # Flow identification part
            # Key Tuple =  (source port, source IP address, destination port, destination IP address)
            key = (tcp.sport, inet_to_str(ip.src), tcp.dport, inet_to_str(ip.dst))
            alt_key = (tcp.dport, inet_to_str(ip.dst), tcp.sport, inet_to_str(ip.src))

            # SYN Check for Flow Start
            # We want the very first packet which means that it has the SYN flag but not an ACK flag
            if (tcp.flags & dpkt.tcp.TH_SYN) and not (tcp.flags & dpkt.tcp.TH_ACK):
                # Add key and initialize into flows if not in it
                if key not in flows:
                    flows[key] = {
                        'start': timestamp,
                        'end': 0,
                        'packets': [current_pkt],
                        'transmitted': {},
                        'RTT': -timestamp,
                        'congestion_window': [0, 0, 0],
                        'ranges': [0, 0, 0, 0],
                        'size': current_pkt['tcp'].opts[-1]
                    }
                else:
                    flows[key]['packets'].append(current_pkt)
            # FIN Check for Flow End
            # We want the very last packet which means that it has the FIN flag. Also check to make sure its in flows.
            elif tcp.flags & dpkt.tcp.TH_FIN and key in flows:
                flows[key]['end'] = timestamp
                flows[key]['packets'].append(current_pkt)
            # Intermediate Packets, add to flow
            elif key in flows:
                if timestamp < flows[key]['start']:
                    flows[key]['start'] = timestamp
                flows[key]['packets'].append(current_pkt)
                flows[key]['end'] = timestamp
            # Reverse direction packets
            else:
                flows[alt_key]['packets'].append(current_pkt)

            # RTT Determination
            if (tcp.flags & dpkt.tcp.TH_SYN) and (tcp.flags & dpkt.tcp.TH_ACK):
                if alt_key in flows:
                    flows[alt_key]['RTT'] += timestamp

            # Congestion Window Determination
            if key in flows:
                flow, trans = flows[key], flows[key]['transmitted']
                for i in range(3):
                    if flow['ranges'][i] <= timestamp <= flow['ranges'][i + 1]:
                        flow['congestion_window'][i] += 1
                if tcp.seq not in trans:
                    trans[tcp.seq] = [[timestamp], 1]
                elif tcp.flags & dpkt.tcp.TH_PUSH:
                    for i in range(4):
                        flow['ranges'][i] = timestamp + i * flow['RTT']
                else:
                    trans[tcp.seq][0].append(timestamp)
                    trans[tcp.seq][1] += 1
        except Exception:
            continue
    return flows


# Helper Function to print our key items
def key_printer(i, key):
    print("--------------------------------------")
    print(f"Flow {i + 1}: Source: ({key[1]}:{key[0]}) -> Destination: Source: ({key[3]}:{key[2]})")
    print("The order below is Transaction 1 Sender -> Receiver then Transaction 2 Sender -> Receiver")
    print("And then it is Transaction 1 Receiver -> Sender then Transaction 2 Receiver -> Sender")


# Helper Function to print the direction of the packet movement
def printer(sender, receiver, packet, rws):
    print(f"{sender} -> {receiver}: SEQ: {packet.seq} ACK: {packet.ack} RWS: {rws}")


# Helper Function to calculate and print throughput
def byte_printer(packets, value, key):
    # sums up the total bytes and then calculates the throughput
    total_bytes = sum(len(packet['tcp']) for packet in packets if packet['src'] != key[3] or packet['dst'] != key[1])
    print(
        f"Total Bytes Sent: {total_bytes}, Duration: {value['end'] - value['start']}, Throughput: {total_bytes / (value['end'] - value['start'])}")


# Helper Function to print retransmission statistics
def retransmission_printer(packets, value):
    # Time out and Duplicate Counters.
    timeout_count = sum(
        1 for packet in packets.values() if packet[1] > 1 and max(packet[0]) - min(packet[0]) > 2 * value['RTT'])
    duplicate_count = sum(
        1 for packet in packets.values() if packet[1] > 1 and not max(packet[0]) - min(packet[0]) > 2 * value['RTT'])
    print(f"Retransmission Statistics: (Triple ACK Retransmissions: {duplicate_count}) + "
          f"(Timeout Retransmissions: {timeout_count}) = (Total Retransmissions: {timeout_count + duplicate_count})")


# Analyzes flows and determines
def flows_analyzer(flow_list):
    for i, (key, value) in enumerate(flow_list.items()):
        stat_track = {
            'send_count': 0,
            'receive_count': 0,
            'handshake_count': 0,
            'receive_window_size': 0,
        }
        packets = sorted(value['packets'], key=lambda ft: ft['timestamp'])
        for j, packet in enumerate(packets):
            stat_track['receive_window_size'] = packet['tcp'].win << value['size']
            # Begin the counting
            if packet['syn']:
                if packet['src'] == key[1] and packet['dst'] == key[3]:
                    stat_track['handshake_count'] += 1
                    key_printer(i, key)
                elif packet['src'] == key[3] and packet['dst'] == key[1]:
                    stat_track['handshake_count'] += 1
            elif packet['ack'] and not packet['fin']:
                # Sender to Receiver transaction
                if packet['src'] == key[1] and packet['dst'] == key[3]:
                    if not (2 <= stat_track['handshake_count'] <= 3):
                        print("Bruh! Handshake was never completed!")
                    elif stat_track['handshake_count'] == 2:
                        stat_track['handshake_count'] += 1
                    elif stat_track['handshake_count'] == 3:
                        if stat_track['send_count'] < 2:
                            printer("Sender", "Receiver", packet['tcp'], stat_track['receive_window_size'])
                            stat_track['send_count'] += 1
                # Receiver to Sender transaction
                elif packet['src'] == key[3] and packet['dst'] == key[1]:
                    if stat_track['receive_count'] < 2:
                        printer("Receiver", "Sender", packet['tcp'], stat_track['receive_window_size'])
                    stat_track['receive_count'] += 1
            # When a fin is received, we will print the statistics of this flow
            elif packet['fin']:
                byte_printer(packets, value, key)
                retransmission_printer(value['transmitted'], value)
                print("Estimated Window Size:", value['congestion_window'])
                break


flows_analyzer(flow_info(init_pcap_bytes()))
