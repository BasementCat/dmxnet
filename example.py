import threading
import time

from dmxnet import ESP


node = ESP(bind_address=('', 1234), node_data='foobar')
client = ESP(send_port=1234)


def mk_handle_poll_reply(name):
    def handle_poll_reply(addr, type_, args, data):
        print(f"[{name}] Poll reply from {addr}: {args}, {data}")
    return handle_poll_reply

def mk_handle_dmx(name):
    def handle_dmx(universe, start_addr, channels):
        print(f"[{name}] DMX universe {universe}@{start_addr}: {channels}")
    return handle_dmx

def mk_handle_ack(name):
    def handle_ack(addr, type_, args, data):
        print(f"[{name}] ACK from {addr}: {args}")
    return handle_ack

def mk_handle_reset(name):
    def handle_reset(addr, type_, args, data):
        print(f"[{name}] RESET from {addr}: {args}")
    return handle_reset


stop = threading.Event()
def run():
    try:
        while not stop.is_set():
            node.process_packet(poll_reply_cb=mk_handle_poll_reply('NODE'), dmx_cb=mk_handle_dmx('NODE'), ack_cb=mk_handle_ack('NODE'), reset_cb=mk_handle_reset('NODE'))
            client.process_packet(poll_reply_cb=mk_handle_poll_reply('CLIENT'), dmx_cb=mk_handle_dmx('CLIENT'), ack_cb=mk_handle_ack('CLIENT'), reset_cb=mk_handle_reset('CLIENT'))
    finally:
        node.close()
        client.close()


t = threading.Thread(target=run)
t.start()

client.send_poll()
for i in range(4):
    for chan in range(512):
        client.set_channel(chan + 1, 0)
    for chan in range(i * 128, (i * 128) + 128):
        client.set_channel(chan + 1, 255)
    client.send_dmx(universe=i)

time.sleep(1)
stop.set()
while t.is_alive():
    pass

# import time
# t = time.time()
# while True:
#     try:
#         node.process_packet(poll_reply_cb=handle_poll_reply, dmx_cb=handle_dmx)
#     except BlockingIOError:
#         if time.time() - t >= 3:
#             raise

    # def set_channel(self, chan, level):
    #     # Note that the channel is 1-512, not 0-indexed
    #     self.dmx_data[chan - 1] = level

    # def send_poll(self, *, address=None, reply_type=None):
    #     if reply_type is None:
    #         reply_type = self.REPLY_FULL
    #     return self._send('POLL', address=address, reply_type=reply_type)

    # def send_poll_reply(self, *, address=None, serial_number=None, node_type=None, node_version=None, switches=0, name=None, option=0, tos=0, ttl=10, node_data=None):
    #     return self._send(
    #         'POLL_REPLY',
    #         data=node_data or self.node_data,
    #         mac=serial_number or self.serial_number,
    #         node_type=node_type or self.node_type,
    #         version=node_version or self.node_version,
    #         switches=switches,
    #         name=name or self.name,
    #         option=option,
    #         tos=tos,
    #         ttl=ttl
    #     )

    # def send_dmx(self, *, address=None, universe=None):
    #     data = bytes(bytearray(self.dmx_data))
    #     return self._send(
    #         'DMX',
    #         address=address,
    #         data=data,
    #         universe=self.universe if universe is None else universe,
    #         start_code=0,
    #         data_type=1,
    #         data_size=len(data)
    #     )

    # def send_ack(self, *, address=None, ack_err=None, crc=None):
    #     if ack_err is None:
    #         if crc is None:
    #             status = 255
    #         else:
    #             status = 0
    #     else:
    #         status = ack_err
    #     return self._send('ACK', address=address, status=status, crc=crc or 0)

    # def send_reset(self, *, address=None, serial_number=None):
    #     return self._send('RESET', address=address, mac=serial_number or self.serial_number)

    # def process_packet(self, *, poll_cb=None, poll_reply_cb=None, ack_cb=None, dmx_cb=None, reset_cb=None):
    #     addr, type_, args, crc = self._recv()
    #     if type_ is None:
    #         return

    #     self.send_ack(address=addr[0], crc=crc)
    #     if type_ == 'POLL':
    #         if poll_cb:
    #             poll_cb(addr, type_, args, crc)
    #         else:
    #             self.poll_reply(address=addr[0])
    #     elif type_ == 'POLL_REPLY':
    #         if poll_reply_cb:
    #             poll_reply_cb(addr, type_, args, crc)
    #     elif type_ == 'ACK':
    #         if ack_cb:
    #             ack_cb(addr, type_, args, crc)
    #     elif type_ == 'DMX':
    #         if dmx_cb:
    #             dmx_cb(args['universe'], args['start_code'], list(map(ord, args['data'])))
    #     elif type_ == 'RESET':
    #         if reset_cb:
    #             reset_cb(addr, type_, args, crc)
    #         elif dmx_cb:
    #             dmx_cb(None, 0, [self.default_level] * 512)
