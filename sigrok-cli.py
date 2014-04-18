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

context = Context()

if args.version:
    print sys.argv[0], VERSION
    print "\nUsing libsigrok %s (lib version %s)." % (
        context.package_version, context.lib_version)
    print "\nSupported hardware drivers:\n"
    for driver in context.drivers.values():
        print "  %-20s %s" % (driver.name, driver.longname)
    print "\nSupported input formats:\n"
    for input in context.input_formats.values():
        print "  %-20s %s" % (input.id, input.description)
    print "\nSupported output formats:\n"
    for output in context.output_formats.values():
        print "  %-20s %s" % (output.id, output.description)
    print
    sys.exit(0)

if args.loglevel:
    context.loglevel = LogLevel.get(int(args.loglevel))

def print_device_info(device):
    print "%s - %s with %d channels: %s" % (device.driver.name, str.join(' ',
            [s for s in (device.vendor, device.model, device.version) if s]),
        len(device.channels), str.join(' ', [c.name for c in device.channels]))

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

    input_file = InputFile(format, args.input_file)

    device = input_file.device

elif args.driver:

    driver = context.drivers[args.driver]

    driver_options = {}

    if args.config:
        pairs = args.config.split(':')
        for pair in pairs:
            name, value = pair.split('=')
            key = getattr(ConfigKey, name)
            driver_options[name] = key.parse_string(value)

    devices = driver.scan(**driver_options)

    if args.scan:
        for device in devices:
            print_device_info(device)
        sys.exit(0)

    device = devices[0]

    device.open()

    if args.channel_group:
        obj = device.channel_groups[args.channel_group]
    else:
        obj = device

    for key, value in driver_options.items():
        setattr(obj, key, value)

    if args.time:
        device.config_set(ConfigKey.LIMIT_MSEC, args.time)
    if args.samples:
        device.config_set(ConfigKey.LIMIT_SAMPLES, args.samples)
    if args.frames:
        device.config_set(ConfigKey.LIMIT_FRAMES, args.frames)

if args.channels:
    enabled_channels = set(args.channels.split(','))
    for channel in device.channels.values():
        channel.enabled = (channel.name in enabled_channels)

if args.set:
    device.close()
    sys.exit(0)

session = Session(context)

if args.driver:
    session.add_device(device)
    session.start()

output = Output(context.output_formats[args.output_format], device)

def datafeed_in(device, packet):
    text = output.receive(packet)
    if text:
        print text,

session.add_callback(datafeed_in)

if args.input_file:
    input_file.load()
    session.stop()
else:
    if args.continuous:
        signal(SIGINT, lambda signum, frame: session.stop())
    session.run()
    if not args.continuous:
        session.stop()
    device.close()
