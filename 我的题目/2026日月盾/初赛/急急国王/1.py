import random
import threading
import queue
import signal
from Crypto.Util.number import *

with open("flag.txt", "r") as f:
    flag = f.read().strip().encode()

def input_with_timeout(prompt, timeout):
    q = queue.Queue()

    def get_input():
        try:
            q.put(input(prompt))
        except EOFError:
            q.put(None)

    thread = threading.Thread(target=get_input, daemon=True)
    thread.start()

    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return None

def interactive_quiz():
    ops = ['+', '-', '*', '/']

    score = 0
    total = 0
    for _ in range(100):
        op = random.choice(ops)

        if op == '/':
            b = random.randint(1, 2 ** 40)
            ans = random.randint(1, 2 ** 40)
            a = b * ans

        elif op == '-':
            a = random.randint(1, 2 ** 40)
            b = random.randint(1, a)
            ans = a - b

        elif op == '*':
            a = random.randint(1, 2 ** 40)
            b = random.randint(1, 2 ** 40)
            ans = a * b

        else:
            a = random.randint(1, 2 ** 40)
            b = random.randint(1, 2 ** 40)
            ans = a + b

        user_input = input_with_timeout(f"题目 {total + 1} / {100}: {a} {op} {b} = ",5)

        if user_input is None:
            print(f"\nYou are so slow!!!\n")
            exit(0)

        try:
            user_ans = float(user_input)
        except ValueError:
            print("\nWrong input!\n")
            exit(0)

        total += 1

        # 答案错误
        if abs(user_ans - ans) < 1e-6:
            score += 1
        else:
            print("\nWrong input!\n")
            break

if __name__ == "__main__":
    print("You are only eligible to proceed with the challenge if you answer my question correctly within 5 seconds!!!")
    interactive_quiz()
    print("\nNow your challenge is as follows,and you have only 1 minute!!!\n")
    if hasattr(signal, "alarm"):   # Windows 本地调试用，Linux 上行为不变
        signal.alarm(60)

    m = getPrime(280)
    e = 65537
    p, q, r = getPrime(256), getPrime(256), getPrime(256)
    n = p * q * r

    phi = (p - 1) * (q - 1) * (r - 1)
    n2 = p * q
    c = pow(m, e, n2)

    print("\nSome parameters of RSA are as follows:\n")
    print(f"n = {n}")
    print(f"phi = {phi}")
    print(f"c = {c}")

    temp = int(input("\nTell me the value of m: "))
    if temp == m:
        print(f"Great!!!Here is your flag: {flag}")
        exit(0)
    else:
        print("\nWrong input!\n")
        exit(0)
