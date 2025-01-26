import socket
import threading
import time

# FLAGS
# START_CON , ACK , FIN_CON


class ClientSelectiveRepeat:
    def __init__(self, file_name, window_size=2) -> None:
        self.file_name = file_name  # To keep file name related client
        self.window_size = window_size
        self.sequence = 0
        self.last_received = 0
        self.can_be_sent = window_size
        self.max_sequence = (
            window_size * 2
        )  # this number can't be reached, will be used for mod operations
        self.window = [False] * window_size

    def __progress(self):
        list_start = 0
        while list_start < len(self.window) and self.window[list_start]:
            print("first element is received, progressing....")
            self.window[list_start] = (
                False  # To use the window like rounded list. opening some areas to it
            )
            self.last_received = (1 + self.last_received) % self.max_sequence
            list_start += 1
            self.can_be_sent += 1

    def __check_sequence(self, seq):
        # window_min = (self.last_received - self.window_size + 1) % self.max_sequence
        window_max = (self.last_received + self.window_size - 1) % self.max_sequence

        # Here, I am handling the problem where the window size is lower then last_received,
        # as they are increasing rounded I need to know which seq number is old.
        if self.last_received > window_max:
            if seq > window_max and seq < self.last_received:
                # Old sequence
                return False
            # In the rage
            return True

        if seq < self.last_received or seq > window_max:
            # Old sequence
            return False
        # In the rage
        return True

    def receive(self, seq):  # After recieving a package
        if not self.__check_sequence(seq):
            # if sequenc number is not in the area we are looking send ack about it because it is already taken
            return seq + 1

        # before acking find the correct location of seq at the window
        converted_seq = (self.last_received + seq) % self.window_size
        print("converted_seq = ", converted_seq)

        self.window[converted_seq] = True  # sign package as received
        self.__give_info()
        self.__progress()
        return (seq + 1) % (self.max_sequence)  # return the package which will be acked

    def __give_info(self):
        print(
            f"ClientRepeaterLog--\nlast received:{self.last_received}, window: {self.window},max sequence number: {self.max_sequence}"
        )


# TODO Dont forget to join all threads before finishing.
class Client:
    def __init__(self, host="127.0.0.1", port=5006, buffer_size=1024) -> None:
        self.buffer_size = buffer_size
        self.host = host
        self.port = port
        self.server_address = (host, 5005)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.sequence = 0
        self.max_payload_size = 255
        self.repeater = None
        self.timeout = 0.001

    def __take_file(self, data):
        data_size = data[1]
        seq_num = data[2]
        data = data[3 : 3 + data_size]
        if self.repeater is None:
            print("Repeater is not initialized!!")
            return
        print("incoming data with sequence number:", seq_num, "data =", data)
        ack_num = self.repeater.receive(seq_num)
        # time.sleep(0.5)
        self.__send_ACK(ack_num)

    def __int_to_bytes(self, num: int):
        return num.to_bytes(1, "big")

    def __send_ACK(self, ack_num: int):

        self.__unreliableSend(
            b"\x01" + self.__int_to_bytes(ack_num), self.server_address
        )

    def __close_con(self):
        # send ack to server.
        self.__unreliableSend(
            b"\x01" + self.__int_to_bytes(self.sequence), self.server_address
        )
        # send fin bit
        self.__unreliableSend(
            b"\x03" + self.__int_to_bytes(self.sequence), self.server_address
        )

        # wait for ack if timeout send fin again.
        self.socket.setblocking(False)
        # while True:
        # wait duplicate of time out before close
        time.sleep(2 * self.timeout)
        try:
            data = self.__unreliableRecv()
            if data[0] == 1:
                print("Fin ACKed, stopping")
        except Exception:
            # if nothing came close.
            pass
        self.sequence = 0
        print("connection closing...")

    def __listener(self):
        print("listening port: ", self.port)
        while True:
            data, addr = self.__unreliableRecv()
            if data[0] == 1:
                print("last message arrived")  ## after this update sequencer
            elif data[0] == 2:  # this means file coming
                self.__take_file(data)
            elif data[0] == 3:
                last_sequence = data[1]
                self.__close_con()
                break
            else:
                print("Unexpected type, not reseolving....", data)

    # TODO: Make this function as main sender
    def __unreliableSend(self, data, addr):
        self.socket.sendto(data, addr)
        print("message sent")

    def __unreliableRecv(self):
        return self.socket.recvfrom(self.buffer_size)

    def listen_port(self):
        # listen_thread = threading.Thread(target=self.__listener)
        print(f"Client starting to listen, server addres: {self.server_address}")
        self.__listener()
        # listen_thread.start()

    def send_input(self):
        print("You can give inputs to send")
        message = input("Enter the file name: ")
        lenght_of_file = len(message)
        # sign as Handshake and add the length of the file
        b_message = b"\x00" + self.__int_to_bytes(lenght_of_file) + message.encode()
        self.socket.sendto(b_message, self.server_address)
        return message

    def connect_to_server(self):
        # sending connection request, bytes 0 is handshake
        file_name = self.send_input()

        # Waiting server to ready to connection
        data, addr = self.socket.recvfrom(self.buffer_size)
        # print(f"received data:{data}")

        if (
            data[0] == 1 and addr == self.server_address
        ):  # Additional control made to reject other requests
            self.socket.sendto(
                b"\x01", self.server_address
            )  # inform server you are ready to connection
            self.segment = 0
            print("Connection established")
            self.repeater = ClientSelectiveRepeat(file_name)
            self.listen_port()  # open port to arrice packages from server
        else:
            # Inform user to connection couldn't established
            print("ACK not taken from server. Closing connection")


client = Client()
client.connect_to_server()
