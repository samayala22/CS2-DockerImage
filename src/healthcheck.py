#!/usr/bin/env python3
import socket, sys, os

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5)
sock.sendto(b'\xFF\xFF\xFF\xFF\x54Source Engine Query\x00', ('127.0.0.1', int(os.getenv("PORT"))))
try:
    sock.recvfrom(4096)
    sys.exit(0)
except socket.timeout:
    sys.exit(1)