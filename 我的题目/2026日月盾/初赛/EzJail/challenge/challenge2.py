from hashlib import sha256
from Crypto.Cipher import AES
from random import *
from Crypto.Util.Padding import *
flag = b'????????'

keys = []
note = b'!!Crypto is nice'
for i in range(4):
    key = bytes(choices(note,k = 3))
    keys.append(sha256(key).digest())

cipher = b'C404 is fun!!!!!'
for i in range(4):
    cipher = AES.new(keys[i], AES.MODE_ECB).encrypt(cipher)

enkey = sha256(b"".join(keys)).digest()
enflag = AES.new(enkey,AES.MODE_ECB).encrypt(pad(flag,AES.block_size))
print(f'cipher = {cipher}')
print(f'enflag = {enflag}')

cipher = b'\xef R\xb5B\xcf\x83tQ\x1a>\x97\xb0\n\x93\xfa'
enflag = b'\x89\xa3\xa1Gmyd\xbckN\xd21\x112\xf5o'