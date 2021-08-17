import random
import time
import re


class Sneakers:
    chars = (
        "○◘◙•♂♀☼▲►▼◄↨↕↔¶¡‼§▬↑↓←→!\"#$%&'()*+,-./0123456789:;=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`"
        "abcdefghijklmnopqrstuvwxyz{|}~⌂ÇâäàåáèéêëíîïÄÅÉæÆòóôöùúûüÿÖÜ¢£¥₧ƒñÑªº¿⌐¬¡»«¼½─"
        "│┌┐└┘├┤┬┴┼═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬▀▄█▌▐■⌠⌡ΓΘΣΦΩαδεπστφ∙√∞∟∩≈≡≤≥"
    )
    ms = 41
    shuffle_each_frame = 36
    reveal_each_frame = 6
    magic_char = "\033[F"

    def __init__(self, text):
        self.encrypted = []
        self.output = []
        self.initial_shuffle_iterations = 24
        self.stage = 0
        self.next_step = None
        self.escape_re = re.compile(r"\x1b[^m]*m")
        self.text = self.escape_re.sub("", text)

    def get_random_char(self):
        return random.choice(self.chars)

    def init_encrypted(self):
        for i, v in enumerate(self.text):
            self.output.append(v)
            if v != " " and v.isprintable():
                self.encrypted.append(i)

    def shuffle(self):
        for i, v in enumerate(self.text):
            if v == " " or not v.isprintable():
                self.output[i] = v
            else:
                self.output[i] = self.get_random_char()

    def reveal_and_shuffle(self):
        for i in range(self.reveal_each_frame):
            if self.encrypted:
                position, value = random.choice(
                    list(enumerate(self.encrypted))
                )
                self.output[value] = self.text[value]
                del self.encrypted[position]
        for i in range(0, self.shuffle_each_frame):
            if self.encrypted:
                position, value = random.choice(
                    list(enumerate(self.encrypted))
                )
                self.output[value] = self.get_random_char()

    def render(self, first=False):
        if first:
            data = "".join(self.output)
        else:
            r = self.magic_char * self.output.count("\n")
            data = f'{r}{"".join(self.output)}'
        print(data, end="\r" if len(self.encrypted) else "\n", flush=True)

    def run(self):
        if self.stage == 0:
            self.initial_shuffle_iterations -= 1
            if self.initial_shuffle_iterations < 1:
                self.stage = 1
                self.next_step = self.reveal_and_shuffle

        else:
            if len(self.encrypted) == 0:
                return False
        return True

    def decrypt(self):
        self.init_encrypted()
        self.next_step = self.shuffle
        self.render(first=True)
        while True:
            self.next_step()
            time.sleep(self.ms / 1000)
            if not self.run():
                break
            self.render()
        self.render()
