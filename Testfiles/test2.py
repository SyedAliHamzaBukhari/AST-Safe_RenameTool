class Processor:
    mode = "active"
    def __init__(self, level):
        self.level = level
        self.count = 0

    def step(self, amount):
        self.count += amount
        return self.count

def helper(level):
    p = Processor(level)
    for n in range(3):
        p.step(n)
    return p.count

def outer():
    text = "Processor should not be renamed inside strings"
    total = 0
    for k in range(4):
        total += k
    return total

value = helper(5)

class Node:
    def __init__(self, name):
        self.name = name

    def rename(self, name):
        self.name = name

root = Node("root")
root.rename("leaf")
print(root.name)
