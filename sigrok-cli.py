##
## This file is part of the sigrok-cli-python project.
##
## Copyright (C) 2013 Martin Ling <martin-sigrok@earth.li>
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

from sigrok.core.classes import *
from signal import signal, SIGINT
from fractions import Fraction
import argparse
import sys

VERSION = "0.1"

parser = argparse.ArgumentParser()
parser.add_argument('-V', '--version', help="Show version", action='store_true')
parser.add_argument('-l', '--loglevel', help="Set log level", type=int)
parser.add_argument('-d', '--driver', help="The driver to use")
parser.add_argument('-c', '--config', help="Specify device configuration options")
parser.add_argument('-i', '--input-file', help="Load input from file")
parser.add_argument('-I', '--input-format', help="Input format")
parser.add_argument('-O', '--output-format', help="Output format", default="bits")
parser.add_argument('-p', '--channels', help="Channels to use")
parser.add_argument('-g', '--channel-group', help="Channel group to use")
parser.add_argument('--scan', help="Scan for devices", action='store_true')
parser.add_argument('--time', help="How long to sample (ms)")
parser.add_argument('--samples', help="Number of samples to acquire")
parser.add_argument('--frames', help="Number of frames to acquire")
parser.add_argument('--continuous', help="Sample continuously", action='store_true')
parser.add_argument('--set', help="Set device options only", action='store_true')

args = parser.parse_args()

if not (args.version
    or args.scan
    or (args.driver and (
            args.set or
            (args.time or args.samples or args.frames or args.continuous)))
    or args.input_file):
    parser.print_help()
    sys.exit(1)

context = Context.create()

if args.version:
    print sys.argv[0], VERSION
    print "\nUsing libsigrok %s (lib version %s)." % (
        context.package_version, context.lib_version)
    print "\nSupported hardware drivers:\n"
    for driver in context.drivers.values():
        print "  %-20s %s" % (driver.name, driver.longname)
    print "\nSupported input formats:\n"
    for input in context.input_formats.values():
        print "  %-20s %s" % (input.name, input.description)
    print "\nSupported output formats:\n"
    for output in context.output_formats.values():
        print "  %-20s %s" % (output.name, output.description)
    print
    sys.exit(0)

if args.loglevel:
    context.loglevel = LogLevel.get(int(args.loglevel))

def print_device_info(device):
    print "%s - %s with %d channels: %s" % (device.driver.name, str.join(' ',
            [s for s in (device.vendor, device.model, device.version) if s]),
        len(device.channels), str.join(' ', [c.name for c in device.get_channels()]))

if args.scan and not args.driver:
    for driver in context.drivers.values():
        devices = driver.scan()
        for device in devices:
            print_device_info(device)
    sys.exit(0)

if args.input_file:

    if args.input_format:
        format = context.input_formats[args.input_format]
    else:
        matched = False
        for format in context.input_formats.values():
            if format.format_match(args.input_file):
                matched = True
                break
        if not matched:
            raise Exception, "File not in any recognised input format."

    device = format.open_file(args.input_file)

elif args.driver:

    driver_spec = args.driver.split(':')

    driver = context.drivers[driver_spec[0]]

    driver_options = {}
    for pair in driver_spec[1:]:
        name, value = pair.split('=')
        key = ConfigKey.get(name)
        driver_options[name] = key.parse_string(value)

    devices = driver.scan(**driver_options)

    if args.scan:
        for device in devices:
            print_device_info(device)
        sys.exit(0)

    device = devices[0]

    device.open()

    for key, name in [
            (ConfigKey.LIMIT_MSEC, 'time'),
            (ConfigKey.LIMIT_SAMPLES, 'samples'),
            (ConfigKey.LIMIT_FRAMES, 'frames')]:
        value = getattr(args, name)
        if value:
            device.config_set(key, key.parse_string(value))

    if args.config:
        for pair in args.config.split(':'):
            name, value = pair.split('=')
            key = ConfigKey.get(name)
            device.config_set(key, key.parse_string(value))

if args.channels:
    enabled_channels = set(args.channels.split(','))
    for channel in device.channels:
        channel.enabled = (channel.name in enabled_channels)

if args.set:
    device.close()
    sys.exit(0)

session = context.create_session()

if args.driver:
    session.add_device(device)
    session.start()

output = context.output_formats[args.output_format].create_output(device)

def datafeed_in(device, packet):
    text = output.receive(packet)
    if text:
        print text,

session.add_datafeed_callback(datafeed_in)

if args.input_file:
    device.load()
    session.stop()
else:
    if args.continuous:
        signal(SIGINT, lambda signum, frame: session.stop())
    session.run()
    if not args.continuous:
        session.stop()
    device.close()
