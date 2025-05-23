#!/usr/bin/env python3
#
# ESP8266 luatool
# Author e-mail: 4ref0nt@gmail.com
# Site: http://esp8266.ru
# Contributions from: https://github.com/sej7278
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51 Franklin
# Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys
import serial
from time import sleep
import socket
import argparse
from os.path import basename


version = "0.6.4"


class TransportError(Exception):
    """Custom exception to represent errors with a transport
    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class AbstractTransport:
    def __init__(self):
        raise NotImplementedError('abstract transports cannot be instantiated.')

    def close(self):
        raise NotImplementedError('Function not implemented')

    def read(self, length):
        raise NotImplementedError('Function not implemented')

    def writeln(self, data, check=1):
        raise NotImplementedError('Function not implemented')

    def writer(self, data):
        self.writeln("file.writeline([==[" + data + "]==])\n")

    def performcheck(self, expected):
        line = ''
        char = ''
        while char != chr(62):  # '>'
            char = self.read(1)
            if char == '':
                raise Exception('No proper answer from MCU')
            if char == chr(13) or char == chr(10):  # LF or CR
                if line != '':
                    line = line.strip()
                    if line+'\r' == expected or line+'\n' == expected:
                        if self.verbose:
                            sys.stdout.write(" -> ok")
                    else:
                        if line[:4] == "lua:":
                            sys.stdout.write("\r\n\r\nLua ERROR: %s" % line)
                            raise Exception('ERROR from Lua interpreter\r\n\r\n')
                        else:
                            expected = expected.split("\r")[0]
                            sys.stdout.write("\r\n\r\nERROR")
                            sys.stdout.write("\r\n send string    : '%s'" % expected)
                            sys.stdout.write("\r\n expected echo  : '%s'" % expected)
                            sys.stdout.write("\r\n but got answer : '%s'" % line)
                            sys.stdout.write("\r\n\r\n")
                            raise Exception('Error sending data to MCU\r\n\r\n')
                    line = ''
            else:
                line += char

    def setverbose(self, verbose=True):
        self.verbose = verbose


class SerialTransport(AbstractTransport):
    def __init__(self, port, baud, noreset):
        self.port = port
        self.baud = baud
        self.serial = None
        self.verbose = False

        try:
            self.serial = serial.Serial(port, baud)
        except serial.SerialException as exception:
            raise TransportError(exception)

        self.serial.flushInput()
        self.serial.flushOutput()
        if not noreset:
            print("do reset..")
            # RTS = either CH_PD or nRESET (both active low = chip in reset)
            # DTR = GPIO0 (active low = boot to flasher)
            self.serial.setRTS(True)
            self.serial.setDTR(False)
            sleep(0.1)
            self.serial.setRTS(False)
            self.serial.setDTR(False)
            sleep(1.5)
            self.serial.timeout = 3
            self.serial.interCharTimeout = 3
            self.serial.write("-- UUUUUUUU\n".encode('latin-1'))
            sleep(0.1)
            print(self.serial.read(9999).decode('latin-1'))
            self.serial.flushInput()
            self.serial.flushOutput()

            self.serial.timeout = 3
            self.serial.interCharTimeout = 3
            print("..reset done")

    def writeln(self, data, check=1):
        if self.serial.inWaiting() > 0:
            self.serial.flushInput()
        if len(data) > 0 and self.verbose:
            sys.stdout.write("\r\n->")
            sys.stdout.write(data.split("\r")[0])
        self.serial.write(data.encode('latin-1'))
        sleep(0.1)
        if check > 0:
            self.performcheck(data)
        elif self.verbose:
            sys.stdout.write(" -> send without check\r\n")

    def read(self, length):
        return self.serial.read(length).decode('latin-1')

    def close(self):
        self.serial.flush()
        self.serial.close()


class TcpSocketTransport(AbstractTransport):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.verbose = False

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as exception:
            raise TransportError(exception)

        try:
            self.socket.connect((host, port))
        except socket.error as e:
            raise TransportError(e.strerror)
        # read intro from telnet server (see telnet_srv.lua)
        self.socket.settimeout(0.5)
        try:
            self.socket.recv(50)
        except socket.error:
            pass
        self.socket.settimeout(3.0)
	#self.socket.setsockopt( IPPROTO_TCP, TCP_NODELAY, 1 )

    def writeln(self, data, check=1):
        if len(data) > 0 and self.verbose:
            sys.stdout.write("\r\n->")
            sys.stdout.write(data.split("\n")[0])
        self.socket.sendall(data.encode('latin-1'))
        if check > 0:
            self.performcheck(data)
        elif self.verbose:
            sys.stdout.write(" -> send without check\r\n")
        #sleep(0.3)

    def write(self, data):
        self.socket.sendall(data.encode('latin-1'))
        #self.socket.flush()
        sleep(0.1)

    def read(self, length):
        return self.socket.recv(length).decode('latin-1')

    def close(self):
        self.socket.close()


def decidetransport(cliargs):
    if cliargs.ip:
        data = cliargs.ip.split(':')
        host = data[0]
        if len(data) == 2:
            port = int(data[1])
        else:
            port = 23
        return TcpSocketTransport(host, port)
    else:
        return SerialTransport(cliargs.port, cliargs.baud, cliargs.noreset)


if __name__ == '__main__':
    # parse arguments or use defaults
    parser = argparse.ArgumentParser(description='ESP8266 Lua script uploader.')
    parser.add_argument('-p', '--port',    default='/dev/ttyUSB0', help='Device name, default /dev/ttyUSB0')
    parser.add_argument('-b', '--baud',    default=9600,           help='Baudrate, default 9600')
    parser.add_argument('-f', '--src',     default=None,           help='Source file on computer')
    parser.add_argument('-t', '--dest',    default=None,           help='Destination file on MCU, default to source file name')
    parser.add_argument('-B', '--binary',  action='store_true',    help='Upload as binary (needs sv_conn global in telnet.lua)')
    parser.add_argument('-c', '--compile', action='store_true',    help='Compile lua to lc after upload')
    parser.add_argument('-r', '--restart', action='store_true',    help='Restart MCU after upload')
    parser.add_argument('-R', '--noreset', action='store_true',    help='Do not reset MCU before command (only serial)')
    parser.add_argument('-d', '--dofile',  action='store_true',    help='Run the Lua script after upload')
    parser.add_argument('-v', '--verbose', action='store_true',    help="Show progress messages.")
    parser.add_argument('-a', '--append',  action='store_true',    help='Append source file to destination file.')
    parser.add_argument('-g', '--get',     default=None,           help='Get contents of specified file on MCU')
    parser.add_argument('-l', '--list',    action='store_true',    help='List files on device')
    parser.add_argument('-w', '--wipe',    action='store_true',    help='Delete all lua/lc files on device.')
    parser.add_argument('-i', '--id',      action='store_true',    help='Query the modules chip id.')
    parser.add_argument('-e', '--execute', default=None,           help='Execute command.')
    parser.add_argument('--delete',        default=None,           help='Delete a lua/lc file from device.')
    parser.add_argument('--ip',            default=None,           help='Connect to a telnet server on the device (--ip IP[:port])')
    parser.add_argument('-W', '--strip-whitespace',dest='strip',action='store_true',help='Remove leading/trailing whitespace, empty lines and comments')
    parser.add_argument('-A', '--auth',    default=None,           help='send auth tag as comment to provide authorization')
    args = parser.parse_args()

    try:
        transport = decidetransport(args)
    except TransportError as e:
        print(e)
        sys.exit(1)

    if args.verbose:
        transport.setverbose(True)

    if args.auth:
        transport.writeln("-- " + args.auth + "\n",1)

    if args.get:
        transport.writeln("=file.open('" + args.get + "', 'r')\n", 0)
        line = ""
        while True:
            char = transport.read(1)
            if char == '' or char == chr(62):
                break
            line += char

        if char == chr(62):
            char = transport.read(1)

        line = line.strip()
        if line == "nil":
            sys.stderr.write("File %s does not exist on device\n" % args.get)
            sys.exit(1)
        if line != "true":
            raise Exception('No proper answer from MCU')

        # file.readline() includes trailing newlines so they are doubled
        # detect EOF as "nil" followed by single newline and prompt (prompt could appear elsewhere)
        transport.writeln("local l; repeat l = file.readline(); print(l) until l == nil;file.close()\n", 0)

        line = ""
        while True:
            char = transport.read(1)
            if char == '':
                break
            if char == chr(13) or char == chr(10):  # LF or CR
                prevch = char

                # Must be a second newline if still printing the file
                char = transport.read(1)
                if prevch != char:  # EOF, skip previous line ("nil")
                    break

                sys.stdout.write(line + prevch)
                line = ""
                continue

            line += char
        sys.exit(0)

    if args.list:
        transport.writeln("local l = '' for k,v in pairs(file.list()) do l=l..k..'\\t'..v..'\\n' end print(l..'>')\n", 0)
        while True:
            char = transport.read(1)
            if char == '' or char == chr(62):
                break
            sys.stdout.write(char)
        sys.exit(0)

    if args.id:
        transport.writeln("=node.chipid()\n", 0)
        id=""
        while True:
            char = transport.read(1)
            if char == '' or char == chr(62):
                break
            if char.isdigit():
                id += char
        print("\n"+id)
        sys.exit(0)

    if args.wipe:
        transport.writeln("local l = file.list();for k,v in pairs(l) do print(k)end\n", 0)
        file_list = []
        fn = ""
        while True:
            char = transport.read(1)
            if char == '' or char == chr(62):
                break
            if char not in ['\r', '\n']:
                fn += char
            else:
                if fn:
                    file_list.append(fn.strip())
                fn = ''
        for fn in file_list[1:]:  # first line is the list command sent to device
            if args.verbose:
                sys.stderr.write("Delete file {} from device.\r\n".format(fn))
            transport.writeln("file.remove(\"" + fn + "\")\n")
        sys.exit(0)

    if args.delete:
        transport.writeln("file.remove(\"" + args.delete + "\")\n")
        sys.exit(0)

    if args.src:
        if args.dest is None:
            args.dest = basename(args.src)

        # open source file for reading
        try:
            if args.binary:
                f = open(args.src, "rb")
            else:
                f = open(args.src, "rt")
        except:
            sys.stderr.write("Could not open input file \"%s\"\n" % args.src)
            sys.exit(1)

        # Verify the selected file will not exceed the size of the serial buffer.
        # The size of the buffer is 256. This script does not accept files with
        # lines longer than 230 characters to have some room for command overhead.
        if args.binary is None:
            for ln in f:
                if len(ln) > 230:
                    sys.stderr.write("File \"%s\" contains a line with more than 240 "
                                     "characters. This exceeds the size of the serial buffer.\n"
                                     % args.src)
                    f.close()
                    sys.exit(1)

        # Go back to the beginning of the file after verifying it has the correct
        # line length
        f.seek(0)

        # set serial timeout
        if args.verbose:
            sys.stderr.write("Upload starting\r\n")

        if args.binary:
          if args.verbose:
              sys.stderr.write("\r\nSingle Stage: Do Binary Upload")
          transport.writeln("file.open(\"" + args.dest + "\", \"w+\")\n")
          total_len=0
          if args.verbose:
            transport.writeln("sv_recv_total=0 sv_conn:on(\"receive\", function(c,d) node.output(nil) file.write(d) print(d:len()) sv_recv_total=sv_recv_total+d:len() end) sv_conn:on(\"disconnection\", function(c) file.flush() file.close() print(\"Received \"..sv_recv_total..\" bytes\") end)\n",1)
          else:
            transport.writeln("node.output(nil) sv_conn:on(\"receive\", function(c,d) file.write(d) end) sv_conn:on(\"disconnection\", function(c) file.flush() file.close() end)",0)
          sys.stdout.write("\r\n")
          sleep(1)
          while True:
            data = f.read(1400)
            if not data:
                break
            transport.write(data.decode('latin-1'))
            sleep(0.2)
            total_len+=len(data)
            if args.verbose:
                sys.stderr.write("\r\nWrote {} bytes...".format(len(data)))
          f.close()
          sleep(3)
          transport.close()
          if args.verbose:
            sys.stderr.write("\r\nEnd. Uploaded {} bytes, Need to close connection after binary upload\r\n".format(total_len))
          exit(0)

        # read source file line by line and write to device
        if args.verbose:
            sys.stderr.write("\r\nStage 1. Creating file in flash memory and write first line")
        if args.append: 
            transport.writeln("file.open(\"" + args.dest + "\", \"a+\")\n")
        else:
            transport.writeln("file.remove(\"" + args.dest + ".new\") file.open(\"" + args.dest + ".new\", \"w+\")\n")

        if args.verbose:
            sys.stderr.write("\r\nStage 2. Start writing data to flash memory...")

        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if args.strip:
                if line.startswith("--") or len(line) == 0:
                    # Comment or empty line -> skip
                    continue
            transport.writer(line)

        # close both files
        f.close()
        if args.verbose:
            sys.stderr.write("\r\nStage 3. Flush data and closing file")
        transport.writeln("file.flush()\n")
        transport.writeln("file.close()\n")
        if not args.append:
            sleep(1.0)
            transport.writeln("file.remove(\"" + args.dest + "\") file.rename(\"" + args.dest + ".new\", \"" + args.dest + "\")\n")

    # compile?
    if args.compile:
        if args.verbose:
            sys.stderr.write("\r\nStage 4. Compiling")
        transport.writeln("node.compile(\"" + args.dest + "\")\n")
        transport.writeln("file.remove(\"" + args.dest + "\")\n")

    if args.dofile:   # never exec if restart=1
        dofile_name = args.compile and args.dest.replace(".lua", ".lc") or args.dest
        transport.writeln("dofile(\"" + dofile_name + "\")\n", 0)

    if args.execute is not None:
        transport.writeln(args.execute+"\n", 0)
        while True:
            char = transport.read(1)
            if char == '' or char == chr(62):
                sys.stdout.write("\r\n")
                break
            sys.stdout.write(char)

    # restart or dofile
    if args.restart:
        transport.writeln("node.restart()\n", 0)

    # close serial port
    transport.close()

    # flush screen
    sys.stdout.flush()
    sys.stderr.flush()
    if args.verbose:
        sys.stderr.write("\r\n--->>> All done <<<---\r\n")
