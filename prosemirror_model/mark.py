class Mark:
    def __init__(self, type, attrs):
        self.type = type
        self.attrs = attrs

    def add_to_set(self, set):
        copy = None
        placed = False
        for i in range(len(set)):
            other = set[i]
            if self.eq(other):
                return set
            if self.type.excludes(other.type):
                if copy is None:
                    copy = set[0:i]
            elif other.type.excludes(self.type):
                return set
            else:
                if not placed and other.type.rank > self.type.rank:
                    if copy is None:
                        copy = set[0:i]
                    copy.append(self)
                    placed = True
                if copy:
                    copy.append(other)
        if copy is None:
            copy = set[:]
        if not placed:
            copy.append(self)
        return copy

    def remove_from_set(self, set):
        return [item for item in set if not item.eq(self)]

    def is_in_set(self, set):
        return any(item.eq(self) for item in set)

    def eq(self, other):
        if self == other:
            return True
        return self.type.name == other.type.name and self.attrs == other.attrs

    def to_json(self):
        return {"type": self.type.name, "attrs": self.attrs}

    @classmethod
    def from_json(cls, schema, json_data):
        if isinstance(json_data, str):
            import json

            json_data = json.loads(json_data)
        if not json_data:
            raise ValueError("Invalid input for Mark.fromJSON")
        type = schema.marks.get(json_data["type"])
        if not type:
            raise ValueError(f"There is not mark type {type} in this schema")
        return type.create(json_data.get("attrs"))

    @classmethod
    def same_set(cls, a, b):
        if a == b:
            return True
        if len(a) != len(b):
            return False
        return all(item_a.eq(item_b) for (item_a, item_b) in zip(a, b))

    @classmethod
    def set_from(cls, marks):
        if not marks:
            return cls.none
        if isinstance(marks, cls):
            return [marks]
        copy = marks[:]
        return sorted(copy, key=lambda item: item.type.rank)


Mark.none = []
