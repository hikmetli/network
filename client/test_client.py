import socket
import threading
import time
import random


class SelectiveRepeat:
    def __init__(self, window_size=10, max_sequence=100):
        self.window_size = window_size
        self.max_sequence = max_sequence
        self.last_acked_seq = 0
        self.window = [None] * window_size
        self.window_used = [False] * window_size

    def receive_packet(self, seq_num, payload):
        if (
            seq_num < self.last_acked_seq
            or seq_num >= self.last_acked_seq + self.window_size
        ):
            return False

        window_index = seq_num % self.window_size
        self.window[window_index] = payload
        self.window_used[window_index] = True
        return True

    def get_next_expected_seq(self):
        return self.last_acked_seq


class ReliableUDPClient:
    def __init__(self, host="127.0.0.1", port=5006, server_port=5005):
        self.host = host
        self.port = port
        self.server_addr = (host, server_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.settimeout(5)  # 5-second timeout

    def connect(self, filename):
        # Handshake
        handshake_packet = bytes([0]) + bytes([len(filename)]) + filename.encode()
        self.socket.sendto(handshake_packet, self.server_addr)

        selective_repeat = SelectiveRepeat()
        received_data = {}
        fin_received = False

        while not fin_received:
            try:
                data, addr = self.socket.recvfrom(1024)

                if data[0] == 2:  # Data packet
                    payload_length = data[1]
                    seq_num = data[2]
                    payload = data[3 : 3 + payload_length]

                    # Check if packet can be accepted
                    if selective_repeat.receive_packet(seq_num, payload):
                        # Send ACK
                        ack_packet = bytes([1]) + bytes([seq_num])
                        self.socket.sendto(ack_packet, addr)

                        # Store the payload
                        received_data[seq_num] = payload

                elif data[0] == 3:  # FIN packet
                    fin_received = True

            except socket.timeout:
                print("Connection timeout")
                break

        # Reconstruct and save file with original bytes
        if received_data:
            sorted_data = [received_data[key] for key in sorted(received_data.keys())]
            with open(f"received_{filename}", "wb") as f:
                for payload in sorted_data:
                    f.write(payload)

            print(f"File {filename} received successfully")
        else:
            print("No data received")


def run_client(filename):
    client = ReliableUDPClient()
    client.connect(filename)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python script.py filename")
        sys.exit(1)

    run_client(sys.argv[1])
