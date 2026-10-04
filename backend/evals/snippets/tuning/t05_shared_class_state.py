class ShoppingCart:
    # expect: bug
    items = []

    def __init__(self, owner):
        self.owner = owner

    def add(self, item):
        self.items.append(item)

    def total(self):
        return sum(item["price"] for item in self.items)
