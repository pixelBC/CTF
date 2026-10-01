from Crypto.Util.number import getPrime, inverse, GCD
from hashlib import sha512
from pwn import *
import secrets

with open("flag.txt", "r") as f:
    FLAG = f.read().strip().encode()

ROUNDS = 400
ROUND_RANDOM_BYTES = 16
MOVES = (b"rock", b"scissors", b"paper")

def H(i, r):
    return int.from_bytes(sha512(bytes([i]) + r).digest(), "big")

class Commitment:
    def __init__(self):
        while True:
            p, q = getPrime(512), getPrime(512)
            if GCD(p - 1, 65537) == GCD(q - 1, 65537) == 1:
                break
        self.p, self.q = p, q
        self.n, self.e = p * q, 65537
        self.dp = inverse(self.e, p - 1)
        self.dq = inverse(self.e, q - 1)

    def commit(self, value):
        while True:
            mask = secrets.randbits(512)
            if mask and GCD(mask, self.n) == 1:
                break
        return pow(mask, self.e, self.n), value ^ mask

    def open(self, commitment):
        token, masked = commitment
        rp = pow(token, self.dp, self.p)
        rq = pow(token, self.dq, self.q)
        mask = (rp + self.p * ((rq - rp) * inverse(self.p, self.q) % self.q)) % self.n
        return masked ^ mask

COM = Commitment()

def handle(io):
    io.sendline(b"Welcome to C404 2026")
    io.sendline(f"Beat me in RPS game for {ROUNDS} rounds.".encode())
    io.sendline(f"parameters: n = {COM.n}, e = {COM.e}".encode())

    for i in range(1, ROUNDS + 1):
        r = secrets.token_bytes(ROUND_RANDOM_BYTES)
        dealer = secrets.randbelow(3)
        commitment = COM.commit(H(dealer, r))

        io.sendline(f"[round {i}/{ROUNDS}]".encode())
        io.sendline(f"r = {r.hex()}".encode())
        io.sendline(b"I have committed to my move. Now your turn.")
        io.sendline(f"commitment: {commitment}".encode())
        io.send(b"your move [rock/scissors/paper]: ")

        player = MOVES.index(io.recvline().strip())

        io.sendline(f"I played {MOVES[dealer].decode()}.".encode())
        io.sendline(f"You played {MOVES[player].decode()}.".encode())

        if dealer != (player + 1) % 3:
            io.sendline(b"You lose.")
            io.close()
            return

        io.sendline(b"You win this round.")

    io.sendline(b"You win the game!")
    io.sendline(b"flag: " + FLAG)
    io.close()

if __name__ == "__main__":
    context.log_level = "error"
    s = listen(10001)

    while True:
        io = s.wait_for_connection()
        try:
            handle(io)
        except Exception:
            io.close()