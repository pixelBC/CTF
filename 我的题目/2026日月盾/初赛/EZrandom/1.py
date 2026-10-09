import os
import time
import uuid

FLAG = os.environ.get("FLAG", f"C404{uuid.uuid4()}")

class LuckyMachine:
    def __init__(self, seed):
        self.state = seed % (1 << 31)
        self.issued = 0
    def tap(self):
        self.state = (1325799325 * self.state + 32525) % (1 << 31)
        self.issued += 1
        return self.state

def menu():
    print()
    print("[1] Print a number")
    print("[2] Guess next number")
    print("[3] Close")

def main():
    print("Welcome to C404 Random Machine!")
    print("Guests a number. Admins must enter the next number.")
    machine = LuckyMachine(int(time.time()) ^ int.from_bytes(os.urandom(4), "big"))

    while True:
        menu()
        try:
            choice = input("> ")
        except EOFError:
            break

        if choice == "1":
            print("guest number =", machine.tap())
        elif choice == "2":
            code = machine.tap()
            guess = input("next_number = ").strip()
            if guess == str(code):
                print("Nice!!! Here is your flag:")
                print(FLAG)
            else:
                print("Wrong code.")
                print("The machine silently moved on. issued_count =", machine.issued)
        elif choice == "3":
            print("You walk away.")
            break

if __name__ == "__main__":
    main()
