"""远程验证：python solve_remote.py <host> <port>"""
import ast
import sys

from hashlib import sha512
from pwn import remote
from tqdm import trange

MOVES = ("rock", "scissors", "paper")


def H(i, r):
    return int.from_bytes(sha512(bytes([i]) + r).digest(), "big")


def recover_dealer(n, e, r, commitment):
    token, masked = commitment
    for dealer in range(3):
        if pow(masked ^ H(dealer, r), e, n) == token:
            return dealer
    raise RuntimeError("dealer not found")


io = remote(sys.argv[1], int(sys.argv[2]))
io.recvuntil(b"parameters: n = ")
n = int(io.recvuntil(b", e = ", drop=True))
e = int(io.recvline())

for _ in trange(400):
    io.recvuntil(b"r = ")
    r = bytes.fromhex(io.recvline().strip().decode())
    io.recvuntil(b"commitment: ")
    c = ast.literal_eval(io.recvline().decode())
    io.recvuntil(b"your move [rock/scissors/paper]: ")
    io.sendline(MOVES[(recover_dealer(n, e, r, c) - 1) % 3].encode())

io.recvuntil(b"flag: ")
print(io.recvline().decode().strip())
io.close()