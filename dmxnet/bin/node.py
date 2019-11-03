import argparse
import time
import glob
import os

from dmxpy.DmxPy import DmxPy

from dmxnet import ESP


def parse_args():
    p = argparse.ArgumentParser(description="Run a node that translates network data to DMX commands")
    p.add_argument('-t', '--type', default='ESP', choices=['ESP'], help="Node network protocol type")
    p.add_argument('-a', '--address', help="Bind to this address")
    p.add_argument('-p', '--port', type=int, help="Bind to this port")
    p.add_argument('-u', '--universe', type=int, help="Respond only to this DMX universe, default is to respond to all")
    p.add_argument('-d', '--device', default='/dev/ttyUSB0', help="Use this USB device, can be a path to a device file, or a vendor:product ID")
    p.add_argument('-s', '--serial', help="Serial of this node, default is the MAC address")
    p.add_argument('-n', '--name', help="Name of this node, default is the system hostname")

    p.add_argument('--discover', action='store_true', help="Discover nodes on the network, and exit")
    return p.parse_args()


def find_device_file(name):
    # Name is either a path (/dev/ttyUSB0) which might change, or a device ID (0403:6001) which does not
    if name.startswith('/') or ':' not in name:
        # Assume file
        return name

    if ':' not in name:
        raise ValueError(f"Not a valid device ID: {name}")

    hexint = lambda v: int(v, 16)
    vendor, product = map(hexint, name.split(':'))

    for dev in glob.glob('/sys/bus/usb-serial/devices/*'):
        devname = os.path.basename(dev)
        with open(os.path.join(dev, '../uevent'), 'r') as fp:
            for line in fp:
                line = line.strip()
                if line and '=' in line:
                    param, value = line.split('=')
                    if param == 'PRODUCT':
                        testvendor, testproduct = map(hexint, value.split('/')[:2])
                        if testvendor == vendor and testproduct == product:
                            return os.path.join('/dev', devname)

    raise RuntimeError(f"Can't find USB device {name}")


def main():
    args = parse_args()
    if args.discover:
        return discover(args)

    dmx = DmxPy(find_device_file(args.device))

    if args.type == 'ESP':
        return run_esp(args, dmx)
    return -1  # Shouldn't happen as this is validated via argparse


def discover(args):
    def print_reply_esp(addr, type_, args, crc):
        print(f"ESP node {addr[0]}:{addr[1]} {args}")

    esp = ESP()
    esp.send_poll(reply_type=ESP.REPLY_NODE)
    t = time.time()
    while time.time() - t <= 5:
        esp.process_packet(poll_reply_cb=print_reply_esp)

    return 0


def run_esp(args, dmx):
    addr = ''
    if args.address and args.port:
        addr = (args.address, args.port)
    elif args.address:
        addr = args.address
    elif args.port:
        addr = ('', args.port)

    data = {
        'start': time.time(),
        'fps': 0,
        'last_frame': time.time(),
    }
    def node_data(*a):
        data = {
            'uptime': int(time.time() - data['start']),
            'fps': data['fps'],
        }
        data = ';'.join(f'{k}={v}' for k, v in data.items()).encode('utf-8')
        return data

    def handle_dmx(universe, start_code, channels):
        data['fps'] = 2 / (time.time() - data['last_frame'])
        data['last_frame'] = time.time()
        if args.universe is None or universe is None or universe == args.universe:
            for chan, value in enumerate(channels):
                dmx.setChannel(chan + start_code, value)
            dmx.render()

    esp = ESP(
        bind_address=addr,
        serial_number=args.serial,
        name=args.name
    )

    try:
        while True:
            esp.process_packet(poll_reply_data_cb=node_data, dmx_cb=handle_dmx)
    except KeyboardInterrupt:
        pass
