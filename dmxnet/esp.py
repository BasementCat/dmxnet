import struct
import uuid
import logging
import socket
import select

import crc8


logger = logging.getLogger(__name__)


class ESP:
    PACKET_TYPES = {
        'POLL': b'ESPP',
        'POLL_REPLY': b'ESPR',
        'ACK': b'ESAP',
        'DMX': b'ESDD',
        'RESET': b'ESZZ',
    }
    PACKET_TYPES_REV = {v: k for k, v in PACKET_TYPES.items()}

    P_HEADER        = b'>4s'
    P_POLL          = (b'>B', ('reply_type',))  # 0=ack, 1=full info, 2=node-specific
    P_POLL_REPLY    = (b'>6sHBB10sBBB', ('mac', 'node_type', 'version', 'switches', 'name', 'option', 'tos', 'ttl',))  # Might also have data afterwards - rest of packet
    P_ACK           = (b'>BB', ('status', 'crc',))
    P_DMX           = (b'>BBBH', ('universe', 'start_code', 'data_type', 'data_size',))  # DMX data is remainder of data
    P_RESET         = (b'>6s', ('mac',))

    PARSERS = {
        'POLL_REPLY': {
            'mac': lambda v: v.hex(),
            'name': lambda v: v.decode('utf-8').rstrip('\x00'),
        },
        'DMX': {
            'data': lambda v: list(v),
        },
    }

    REPLY_ACK = 0
    REPLY_FULL = 1
    REPLY_NODE = 2

    def __init__(self, *, bind_address=None, send_port=3333, default_level=255, universe=0, node_type=2, node_version=1, serial_number=None, node_data=None, name=None):
        self.bind_address = bind_address
        self.send_port = send_port
        self.default_level = default_level
        self.universe = universe
        self.node_type = node_type
        self.node_version = node_version
        self.serial_number = serial_number
        self.node_data = node_data
        self.name = name or socket.gethostname()

        if self.serial_number is None:
            mac = uuid.getnode()
            ser = ''
            for _ in range(6):
                ser += chr((mac >> 40) & 0xff)
                mac <<= 8
            self.serial_number = ser.encode('latin-1')

        if self.default_level < 0 or self.default_level > 255:
            raise ValueError("Default level must be between 0 and 255")

        self._reset_data(self.default_level)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if bind_address is not None:
            self.sock.bind(self._resolve_address(bind_address, port=3333, broadcast=False))

    def _reset_data(self, value):
        self.dmx_data = [value] * 512

    def _resolve_address(self, addr, port=None, broadcast=True):
        port = port or self.send_port
        if addr is None:
            if broadcast:
                return ('<broadcast>', port)
            return ('', port)
        if isinstance(addr, str):
            return (addr, port)
        return addr

    @staticmethod
    def _byteify(v):
        if v is None or isinstance(v, bytes):
            return v
        if not isinstance(v, str):
            v = str(v)
        return v.encode('utf-8')

    def _send(self, type_, address=None, data=None, **kwargs):
        fmt, fields = getattr(self, 'P_' + type_)
        packet = struct.pack(self.P_HEADER, self.PACKET_TYPES[type_])
        packet += struct.pack(fmt, *(kwargs.get(f, 0) for f in fields))
        if data:
            packet += data
        address = self._resolve_address(address)
        # print("Send to", address, repr(packet))
        self.sock.sendto(packet, address)

    def _recv(self, timeout=1):
        ready, _, _ = select.select([self.sock], [], [], timeout)
        if not ready:
            return None, None, None, None

        data, addr = self.sock.recvfrom(1024)
        if len(data) < 4:
            logger.error("Received a packet that's too short: %s", repr(data))
            return None, None, None, None
        type_ = struct.unpack(self.P_HEADER, data[:4])[0]
        if type_ not in self.PACKET_TYPES_REV:
            logger.error("Received an invalid packet type: %s: %s", repr(data[:4]), repr(data))
            return None, None, None, None
        crc = crc8.crc8()
        crc.update(data)
        crc = crc.digest()[0]
        type_ = self.PACKET_TYPES_REV[type_]
        fmt, fields = getattr(self, 'P_' + type_)
        out = dict(zip(fields, struct.unpack(fmt, data[4:struct.calcsize(fmt) + 4])))
        out['data'] = data[struct.calcsize(self.P_HEADER) + struct.calcsize(fmt):] or None
        for k, v in self.PARSERS.get(type_, {}).items():
            if k in out:
                out[k] = v(out[k])
        return addr, type_, out, crc

    def close(self):
        self.sock.close()

    def set_channel(self, chan, level):
        # Note that the channel is 1-512, not 0-indexed
        self.dmx_data[chan - 1] = level

    def send_poll(self, *, address=None, reply_type=None):
        if reply_type is None:
            reply_type = self.REPLY_FULL
        return self._send('POLL', address=address, reply_type=reply_type)

    def send_poll_reply(self, *, address=None, serial_number=None, node_type=None, node_version=None, switches=0, name=None, option=0, tos=0, ttl=10, node_data=None):
        # TODO: check type
        return self._send(
            'POLL_REPLY',
            address=address,
            data=self._byteify(node_data or self.node_data),
            mac=self._byteify(serial_number or self.serial_number),
            node_type=node_type or self.node_type,
            version=node_version or self.node_version,
            switches=switches,
            name=self._byteify(name or self.name),
            option=option,
            tos=tos,
            ttl=ttl
        )

    def send_dmx(self, *, address=None, universe=None):
        data = bytes(bytearray(self.dmx_data))
        return self._send(
            'DMX',
            address=address,
            data=data,
            universe=self.universe if universe is None else universe,
            start_code=1,
            data_type=1,
            data_size=len(data)
        )

    def send_ack(self, *, address=None, ack_err=None, crc=None):
        if ack_err is None:
            if crc is None:
                status = 255
            else:
                status = 0
        else:
            status = ack_err
        return self._send('ACK', address=address, status=status, crc=crc or 0)

    def send_reset(self, *, address=None, serial_number=None):
        return self._send('RESET', address=address, mac=serial_number or self.serial_number)

    def process_packet(self, *, poll_cb=None, poll_reply_cb=None, poll_reply_data_cb=None, ack_cb=None, dmx_cb=None, reset_cb=None, timeout=1):
        addr, type_, args, crc = self._recv(timeout)
        if type_ is None:
            return

        if type_ not in ('ACK', 'POLL'):
            self.send_ack(address=addr, crc=crc)

        if type_ == 'POLL':
            if poll_cb:
                poll_cb(addr, type_, args, crc)
            else:
                node_data = None
                if poll_reply_data_cb:
                    node_data = poll_reply_data_cb(addr, type_, args, crc)
                self.send_poll_reply(address=addr, node_data=node_data)
        elif type_ == 'POLL_REPLY':
            if poll_reply_cb:
                poll_reply_cb(addr, type_, args, crc)
        elif type_ == 'ACK':
            if ack_cb:
                ack_cb(addr, type_, args, crc)
        elif type_ == 'DMX':
            if dmx_cb:
                dmx_cb(args['universe'], args['start_code'], args['data'])
        elif type_ == 'RESET':
            if reset_cb:
                reset_cb(addr, type_, args, crc)
            elif dmx_cb:
                dmx_cb(None, 0, [self.default_level] * 512)
