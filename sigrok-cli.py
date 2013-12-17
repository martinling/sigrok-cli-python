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
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--driver', help="The driver to use")
parser.add_argument('-O', '--output-format', help="Output format", default="bits")
parser.add_argument('--scan', help="Scan for devices", action='store_true')
parser.add_argument('--time', help="How long to sample (ms)", type=int)
parser.add_argument('--samples', help="Number of samples to acquire", type=int)
parser.add_argument('--frames', help="Number of frames to acquire", type=int)
parser.add_argument('--continuous', help="Sample continuously", action='store_true')

args = parser.parse_args()

if not (args.scan or (
        args.driver and (args.time or args.samples or args.frames or args.continuous))):
    parser.print_help()
    sys.exit(1)

context = Context()

if args.scan:
    for driver in context.drivers.values():
        devices = driver.scan()
        for device in devices:
            print "%s - %s with %d probes: %s" % (device.driver.name, str.join(' ',
                    [s for s in (device.vendor, device.model, device.version) if s]),
                len(device.probes), str.join(' ', sorted(device.probes.keys())))
    sys.exit(0)

driver = context.drivers[args.driver]
device = driver.scan()[0]

if args.time:
    device.limit_msec = args.time
if args.samples:
    device.limit_samples = args.samples
if args.frames:
    device.limit_frames = args.frames

session = Session(context)
session.add_device(device)

output = Output(context.output_formats[args.output_format], device)

def datafeed_in(device, packet):
    text = output.receive(packet)
    if text:
        print text,

session.add_callback(datafeed_in)
session.start()

if args.continuous:
    signal(SIGINT, lambda signum, frame: session.stop())

session.run()

if not args.continuous:
    session.stop()
