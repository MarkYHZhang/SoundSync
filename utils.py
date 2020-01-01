import random
import string


def randomString(stringLength=5):
    letters = string.ascii_lowercase+string.digits
    return ''.join(random.choice(letters) for _ in range(stringLength))