def calc(a, b):
    result = a + b
    for i in range(3):
        result *= i + 1
    return result

class MathOps:
    def add(self, a, b):
        return a + b

    def mul(self, a, b):
        return a * b

def main():
    ops = MathOps()
    r1 = ops.add(2, 3)
    r2 = ops.mul(4, 5)
    combined = calc(r1, r2)
    text = "mul and add should not change in this string"
    return combined

num = main()

def container():
    def inner(v):
        return v * 2
    out = inner(num)
    return out

final = container()
print(final)
