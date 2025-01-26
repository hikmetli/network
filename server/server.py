import socket
import time
import random


class ServerSelectiveRepeat:
    def __init__(self, file_name, window_size=2) -> None:
        self.file_name = file_name  # To keep file name related client
        self.file = open(file_name, "r")
        self.window_size = window_size
        self.sequence = 0
        self.last_acked_seq = 0
        self.can_be_sent = window_size
        # this number can't be reached, will be used for mod operations
        self.max_sequence = window_size * 2
        self.window = [False] * window_size
        self.timers = [None] * window_size
        self.time_out = 1  # TODO change this to 0.001
        self.fin = False
        self.fin_ack = False
        self.last_line_readed = False

        self.window_content = self.__initialize_window_content(window_size)

    def __initialize_window_content(self, window_size):
        window = []
        print("repeater created")
        for i in range(window_size):
            print("loop", i)
            window.append(self.__read_from_file())
        print(window, window_size)
        return window

    def __read_from_file(self):
        # if last line readed then don't add new things to window
        if self.last_line_readed:
            return None
        data = self.file.readline()
        return data

    def __progress(self):
        list_start = 0
        while list_start < self.window_size and self.window[list_start]:
            print("first element is acked, progressing....")
            self.window[list_start] = (
                False  # To use the window like rounded list. opening some areas to it
            )
            data = self.__read_from_file()
            if data == "":
                self.last_line_readed = True
                print("last line readed")
            if not self.last_line_readed:
                self.window_content.append(data)
                self.timers.append(None)
                # remove first element to slide window
                self.timers.pop(0)
                self.window_content.pop(0)
                self.can_be_sent += 1
            self.last_acked_seq = (self.last_acked_seq + 1) % self.max_sequence
            list_start += 1

    # Incoming seq number is the next sequence number, we need to increase it when putting in window
    def ack(self, seq):
        # before acking find the correct location of seq at the window
        converted_seq = (self.last_acked_seq + seq - 1) % self.window_size
        print("converted_seq = ", converted_seq)
        self.window[converted_seq] = True  # ack the package
        # set timer None to know this package is acked
        # self.timers[converted_seq] = None
        self.__progress()
        self.__give_info()

    def sent(self):
        # Here I am setting the timer for this packet
        self.timers[(self.sequence + self.last_acked_seq) % self.window_size] = (
            time.time()
        )
        self.can_be_sent -= 1
        self.sequence = (self.sequence + 1) % (self.max_sequence)
        # Assign current time to handle loss
        return self.sequence

    def finish(self):
        self.file.close()

    def __give_info(self):
        print(
            f"ServerRepeaterLog--\nlast acked:{self.last_acked_seq}, window: {self.window},max sequence number: {self.max_sequence}"
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
        self.socket.setblocking(False)  # Won't block if nothing came in buffer
        self.clients: dict[str, ServerSelectiveRepeat] = {}
        # self.sequencer = ServerSelectiveRepeat(window_size)
        self.window_size = window_size
        self.sended = 0
        self.time_out = 1
        # will be setted after FIN packet ACKED.
        self.finishing_time = 0
        # for debugging
        # self.send_success = [False, True, True, False, True]

    def __int_to_bytes(self, num: int):
        return num.to_bytes(1, "big")

    def __read_file(self, filename, offset):
        pass

    def __send_file_package(self, addr):
        repeater = self.clients.get(addr[0])
        if repeater is None:
            print("Can not send the file, Client not Found!")
            return
        print(
            f"Sending the file..., sequence number = {repeater.sequence}, sended: ",
            self.sended,
            "last_acked:",
            repeater.last_acked_seq,
            "timers : ",
            repeater.timers,
        )
        #     # TODO: read file and send using repeater..
        # TODO wait for ack
        # if f == "" and repeater.last_acked_seq:
        #     print("finishing...")
        #     repeater.fin = True
        #     self.unreliableSend(b"\x03", addr)
        #     return
        while repeater.can_be_sent != 0 and not repeater.fin:
            # send last added ones
            payload = repeater.window_content[
                (repeater.sequence + repeater.last_acked_seq) % repeater.window_size
            ]
            print("win content:", repeater.window_content)
            message = (
                b"\x02"
                + self.__int_to_bytes(len(payload))
                + self.__int_to_bytes(repeater.sequence)
                + payload.encode()
            )

            self.unreliableSend(message, addr)
            self.sended += 1
            repeater.sent()

        # Son paket gönderildi mi kontrolü
        print(self.sended, repeater.last_acked_seq)
        if repeater.last_line_readed and repeater.last_acked_seq == (
            self.sended % repeater.max_sequence
        ):
            print("All data sent and ACKed. Sending FIN...")
            fin_message = b"\x03" + self.__int_to_bytes(repeater.last_acked_seq)
            self.unreliableSend(fin_message, addr)
            repeater.fin = True

    def __ack_packege(self, addr, acked):
        repeater = self.clients.get(addr[0])
        if repeater is None:
            print("Can not ack the package, Client not Found!")
            return

        if repeater.fin:
            repeater.fin_ack = True
            return False  # return this was fin flag to finish
        else:
            repeater.ack(acked)
            return True  # return this wasn't fin flag, so continue

    def __ack_controller(self, repeater, addr):
        # if send operation is not finished
        # I am compering window content 0 with None because if first element is None others aldo None
        # See repeater._progress function to more info
        if not repeater.fin:
            if (
                repeater.last_acked_seq == (self.sended % repeater.max_sequence)
                and repeater.window_content[0] is None
            ):
                repeater.fin = True
                self.__close_connection(repeater)

            # time.sleep(0.05)  # TODO might be removed

            for index, t in enumerate(repeater.timers):
                now = time.time()
                # as sequence number is the next sequence we sent
                sequence = (
                    repeater.sequence - repeater.window_size + index
                ) % repeater.max_sequence
                # print("Controlling the timers...")
                # print("timer:", t, "index:", index)
                if (
                    t is not None
                    and now - t > repeater.time_out
                    and not repeater.window[
                        (sequence - repeater.last_acked_seq) % repeater.window_size
                    ]
                ):
                    print(
                        "sending the sequence again...",
                        sequence,
                        "window value: ",
                        # repeater.window[sequence - repeater.window_size + index],
                        repeater.window,
                        "window content",
                        repeater.window_content,
                        "repeater sequence:",
                        repeater.sequence,
                        "index:",
                        index,
                        "sended",
                        self.sended,
                        "window position:",
                        (sequence - repeater.last_acked_seq) % repeater.window_size,
                        "last_acked_seq:",
                        repeater.last_acked_seq,
                        "repeater_fin:",
                        repeater.fin,
                        "timers",
                        repeater.timers,
                    )
                    payload = repeater.window_content[index]
                    message = (
                        b"\x02"
                        + self.__int_to_bytes(len(payload))
                        + self.__int_to_bytes(sequence)
                        + payload.encode()
                    )
                    self.unreliableSend(message, addr)
                    repeater.timers[index] = now
        if repeater.fin and not repeater.fin_ack:
            fin_message = b"\x03" + self.__int_to_bytes(repeater.last_acked_seq)
            self.unreliableSend(fin_message, addr)
            print("fin message send again...")
            # time.sleep(0.5)

    def __listener(self):
        client = None  ## this will be used to keep track of client
        while True:
            try:
                data, addr = self.socket.recvfrom(self.buffer_size)
                print(f"received message = {data} from {addr}")
                # print(f"type of return address: {type(addr)}")
                if data[0] == 0:
                    print("Handshake request came... accepting")
                    file_size = data[1]
                    # +2 came because starting index is 2
                    file_name = data[2 : file_size + 2]
                    self.__accept_connection(addr, file_name.decode())
                    print("Handshake request accepted, starting to send file...")
                    client = addr
                    self.__send_file_package(addr)
                elif data[0] == 1:
                    print("ACK came, acking...", data[1])
                    acked_sequence = data[1]
                    cont = self.__ack_packege(addr, acked_sequence)
                    if cont:
                        self.__send_file_package(addr)
                    # dont continue wait some time, if FIN received send ACK and close the connection
                    else:
                        time.sleep(2 * self.time_out)
                elif data[0] == 3:
                    self.__close_connection(self.clients[addr[0]])
                    break
            except Exception:
                # there is nothing to process control ack
                if client is not None:
                    repeater = self.clients.get(client[0])
                    # print("not received")
                    if repeater is not None:
                        self.__ack_controller(repeater, client)

    def __close_connection(self, repeater):
        repeater.finish()
        print("closing the connection")

    def __accept_connection(self, addr, file_name):
        self.socket.sendto(b"\x01", addr)  ## inform client accepting the connection
        self.socket.setblocking(True)  # wait till ack came
        ack, ack_addr = self.socket.recvfrom(1024)  ## wait for ACK
        self.socket.setblocking(False)  # release
        if addr == ack_addr and ack[0] == 1:
            print(
                f"ACK came from client, Connection established, address = {addr}, filename = {file_name}"
            )
            repeater = ServerSelectiveRepeat(file_name, self.window_size)
            # add this client to connected clients, initialize it's sequence and repeater.
            self.clients[addr[0]] = repeater
            # controller_thread = threading.Thread(
            #     target=self.__ack_controller,
            #     args=(
            #         repeater,
            #         addr,
            #     ),
            # )
            # controller_thread.start()  # will be stop after finishing the connection

    # TODO add the error logic
    def unreliableSend(self, data, addr, error_rate=70):

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
        # listen_thread = threading.Thread(target=self.__listener)
        print("Server starting to listen")
        # listen_thread.start()
        self.__listener()


server = Server()
# server.recv_from()
server.listen_port()
