x = 10
y = x + 5
def compute(x, y):
    result = x * y
    temp = result + x
    return temp

class Data:
    def __init__(self, value):
        self.value = value
        self.extra = 5

    def update(self, value):
        old = self.value
        self.value = value
        return old

def wrapper():
    a = 3
    b = compute(a, a + 2)
    c = Data(b)
    c.update(b)
    return c.value

msg = "x should not change inside this string"
# x in comment should not be renamed
val = wrapper()

def shadow():
    x = 99
    return x + 1

for i in range(5):
    y += i
print(y)
