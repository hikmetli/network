import socket
import threading
import time
import random


class ServerSelectiveRepeat:
    def __init__(self, file_name, window_size=2) -> None:
        self.file_name = file_name  # To keep file name related client
        self.window_size = window_size
        self.sequence = 0
        self.last_acked = 0
        self.can_be_sent = window_size
        # this number can't be reached, will be used for mod operations
        self.max_sequence = window_size * 2
        self.window = [False] * window_size
        self.timers = [None] * window_size
        self.time_out = 0.01
        self.FIN = False

    def __progress(self):
        list_start = 0
        while list_start < len(self.window) and self.window[list_start]:
            print("first element is acked, progressing....")
            self.window[list_start] = (
                False  # To use the window like rounded list. opening some areas to it
            )
            self.last_acked = (self.last_acked + 1) % self.max_sequence
            self.can_be_sent += 1
            list_start += 1

    # Incoming seq number is the next sequence number, we need to increase it when putting in window
    def ack(self, seq):
        # before acking find the correct location of seq at the window
        converted_seq = (self.last_acked + seq - 1) % self.window_size
        print("converted_seq = ", converted_seq)
        self.window[converted_seq] = True  # ack the package
        self.__progress()
        self.__give_info()

    def sent(self):
        # Here I am setting the timer for this packet
        self.timers[(self.sequence) % self.window_size] = time.time()
        self.can_be_sent -= 1
        self.sequence = (self.sequence + 1) % (self.max_sequence)
        # Assign current time to handle loss
        return self.sequence

    def __give_info(self):
        print(
            f"ServerRepeaterLog--\nlast acked:{self.last_acked}, window: {self.window},max sequence number: {self.max_sequence}"
        )


class Server:
    def __init__(
        self, host="127.0.0.1", port=5005, window_size=2, buffer_size=1024
    ) -> None:
        self.buffer_size = buffer_size
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.clients: dict[str, ServerSelectiveRepeat] = {}
        # self.sequencer = ServerSelectiveRepeat(window_size)
        self.window_size = window_size
        self.sended = 0
        # for debugging
        self.send_success = [False, True, True, False, True]

    def __int_to_bytes(self, num: int):
        return num.to_bytes(1, "big")

    def __send_ACK(self, addr):
        self.socket.sendto(b"\x01", addr)

    def __send_file_package(self, addr):
        repeater = self.clients.get(addr[0])
        if repeater is None:
            print("Can not send the file, Client not Found!")
            return
        print(
            f"Sending the file..., sequence number = {repeater.sequence}, sended: ",
            self.sended,
        )
        #     # TODO: read file and send using repeater..
        f = "selam"
        # TODO wait for ack
        if self.sended >= len(f) and repeater.last_acked >= len(f):
            print("finishing...")
            self.unreliableSend(b"\x03", addr)
            return
        while repeater.can_be_sent != 0:
            payload = f[self.sended]
            message = (
                b"\x02"
                + self.__int_to_bytes(len(payload))
                + self.__int_to_bytes(repeater.sequence)
                + payload.encode()
            )
            self.unreliableSend(message, addr)
            repeater.sent()
            self.sended += 1

    def __ack_packege(self, addr, acked):
        repeater = self.clients.get(addr[0])
        if repeater is None:
            print("Can not ack the package, Client not Found!")
            return
        repeater.ack(acked)

    def __ack_controller(self, repeater, addr, f="selam"):
        # if repeater.can_be_sent == 0:
        while not repeater.FIN:
            if self.sended >= len(f) and repeater.last_acked >= len(f):
                repeater.FIN = True
                self.__close_connection(repeater)
                break

            time.sleep(0.55)  # TODO might be removed
            now = time.time()
            for index, t in enumerate(repeater.timers):
                # as sequence number is the next sequence we sent
                sequence = (
                    repeater.sequence - repeater.window_size + index
                ) % repeater.max_sequence
                # print("Controlling the timers...")
                if (
                    t is not None
                    and now - t > repeater.time_out
                    and not repeater.window[
                        (sequence - repeater.last_acked) % repeater.window_size
                    ]
                ):
                    print(
                        "sending the sequence again...",
                        sequence,
                        "window value: ",
                        # repeater.window[sequence - repeater.window_size + index],
                        repeater.window,
                        "repeater sequence:",
                        repeater.sequence,
                        "index:",
                        index,
                        "sended",
                        self.sended,
                        "window position:",
                        (sequence - repeater.last_acked) % repeater.window_size,
                    )
                    payload = f[self.sended - repeater.window_size + index]
                    message = (
                        b"\x02"
                        + self.__int_to_bytes(len(payload))
                        + self.__int_to_bytes(sequence)
                        + payload.encode()
                    )
                    self.unreliableSend(message, addr)

    def __listener(self):
        while True:
            data, addr = self.socket.recvfrom(self.buffer_size)
            print(f"received message = {data} from {addr}")
            # print(f"type of return address: {type(addr)}")
            if data[0] == 0:
                print("Handshake request came... accepting")
                file_size = data[1]
                file_name = data[
                    2 : file_size + 2
                ]  # +2 came because starting index is 2
                self.__accept_connection(addr, file_name.decode())
                print("Handshake request accepted, starting to send file...")
                self.__send_file_package(addr)
            elif data[0] == 1:
                print("ACK came, acking...", data[1])
                acked_sequence = data[1]
                self.__ack_packege(addr, acked_sequence)

                self.__send_file_package(addr)

            elif data[0] == 3:
                self.__close_connection(self.clients[addr[0]])
                break

    def __close_connection(self, repeater):
        repeater.FIN = True
        print("closing the connection")

    def __accept_connection(self, addr, file_name):
        self.socket.sendto(b"\x01", addr)  ## inform client accepting the connection
        ack, ack_addr = self.socket.recvfrom(1024)  ## wait for ACK
        if addr == ack_addr and ack[0] == 1:
            print(
                f"ACK came from client, Connection established, address = {addr}, filename = {file_name}"
            )
            repeater = ServerSelectiveRepeat(file_name, self.window_size)
            # add this client to connected clients, initialize it's sequence and repeater.
            self.clients[addr[0]] = repeater
            controller_thread = threading.Thread(
                target=self.__ack_controller,
                args=(
                    repeater,
                    addr,
                ),
            )
            controller_thread.start()  # will be stop after finishing the connection

    # TODO add the error logic
    def unreliableSend(self, data, addr, error_rate=30):

        if random.randint(1, 100) < error_rate:
            # if self.send_success[self.sended]:
            print("message sent, ", data.decode())
            self.socket.sendto(data, addr)
        else:
            print("message couldn't sent, data:", data.decode())

    def unreliableRecieve(self):
        return self.socket.recvfrom(1024)

    def prepare_dest_address(self, host, port):
        return (host, port)

    def listen_port(self):
        # TODO: this might be removed
        listen_thread = threading.Thread(target=self.__listener)
        print("Server starting to listen")
        listen_thread.start()


server = Server()
# server.recv_from()
server.listen_port()
