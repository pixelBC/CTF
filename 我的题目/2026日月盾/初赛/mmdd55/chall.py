from hashlib import md5

_H = lambda m: md5(m).digest()
S = set()

FLAG = open("flag.txt").read().strip()

print("Every round construct 9 different hex values A,B,C,D,E,F,G,H,I")
print("md(A) = md(B) = md(C)")
print("md(md(A) + D) = md(md(B) + E) = md(md(C) + F)")
print("md(md(md(A) + D) + G) = md(md(md(B) + E) + H) = md(md(md(C) + F) + I)")

for j in range(10):
    print(f"round {j + 1} / 10")

    A, B, C = bytes.fromhex(input('A > ')), bytes.fromhex(input('B > ')), bytes.fromhex(input('C > '))
    ha, hb, hc = _H(A), _H(B), _H(C)
    assert ha == hb == hc

    D, E, F = bytes.fromhex(input('D > ')), bytes.fromhex(input('E > ')), bytes.fromhex(input('F > '))
    hd, he, hf = _H(ha + D), _H(hb + E), _H(hc + F)
    assert hd == he == hf

    G, H, I = bytes.fromhex(input('G > ')), bytes.fromhex(input('H > ')), bytes.fromhex(input('I > '))
    assert _H(hd + G) == _H(he + H) == _H(hf + I)

    cur = (A, B, C, D, E, F, G, H, I)
    assert len(set(cur)) == 9
    assert not any(x in S for x in cur)
    S.update(cur)

print('good:' + FLAG)
