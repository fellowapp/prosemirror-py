lower16 = 0xFFFF
factor16 = 2 ** 16


def make_recover(index, offset):
    return int(index + offset * factor16)


def recover_index(value):
    return int(value & lower16)


def recover_offset(value):
    return int((value - (value & lower16)) / factor16)


class MapResult:
    def __init__(self, pos, deleted=False, recover=None):
        self.pos = pos
        self.deleted = deleted
        self.recover = recover


class StepMap:
    def __init__(self, ranges, inverted=False):
        self.ranges = ranges
        self.inverted = inverted

    def recover(self, value):
        diff = 0
        index = recover_index(value)
        if not self.inverted:
            for i in range(index):
                diff += self.ranges[i * 3 + 2] - self.ranges[i * 3 + 1]
        return self.ranges[index * 3] + diff + recover_offset(value)

    def map_result(self, pos, assoc=1):
        return self._map(pos, assoc, False)

    def map(self, pos, assoc=1):
        return self._map(pos, assoc, True)

    def _map(self, pos, assoc, simple):
        diff = 0
        old_index = 2 if self.inverted else 1
        new_index = 1 if self.inverted else 2
        for i in range(0, len(self.ranges), 3):
            start = self.ranges[i] - (diff if self.inverted else 0)
            if start > pos:
                break
            old_size = self.ranges[i + old_index]
            new_size = self.ranges[i + new_index]
            end = start + old_size
            if pos <= end:
                if not old_size:
                    side = assoc
                elif pos == start:
                    side = -1
                elif pos == end:
                    side = 1
                else:
                    side = assoc
                result = start + diff + (0 if side < 0 else new_size)
                if simple:
                    return result
                recover = None if pos == (start if assoc < 0 else end) else make_recover(i / 3, pos - start)
                return MapResult(
                    result, pos != start if assoc < 0 else pos != end, recover
                )
            diff += new_size - old_size
        return pos + diff if simple else MapResult(pos + diff)

    def touches(self, pos, recover):
        diff = 0
        index = recover_index(recover)
        old_index = 2 if self.inverted else 1
        new_index = 1 if self.inverted else 2
        for i in range(len(self.ranges), 3):
            start = self.ranges[i] - (diff if self.inverted else 0)
            if start > pos:
                break
            old_size = self.ranges[i + old_index]
            end = start + old_size
            if pos <= end and i == index * 3:
                return True
            diff += self.ranges[i + new_index] - old_size
        return False

    def for_each(self, f):
        old_index = 2 if self.inverted else 1
        new_index = 1 if self.inverted else 2
        i = 0
        diff = 0
        while i < len(self.ranges):
            start = self.ranges[i]
            old_start = start - (diff if self.inverted else 0)
            new_start = start + (0 if self.inverted else diff)
            old_size = self.ranges[i + old_index]
            new_size = self.ranges[i + new_index]
            f(old_start, old_start + old_size, new_start, new_start + new_size)
            i += 3

    def invert(self):
        return StepMap(self.ranges, not self.inverted)

    def __str__(self):
        return ("-" if self.inverted else "") + str(self.ranges)


StepMap.empty = StepMap([])


class Mapping:
    def __init__(self, maps=None, mirror=None, from_=None, to=None):
        self.maps = maps or []
        self.from_ = from_ or 0
        self.to = len(self.maps) if to is None else to
        self.mirror = mirror

    def slice(self, from_=0, to=None):
        if to is None:
            to = len(self.maps)
        return Mapping(self.maps, self.mirror, from_, to)

    def copy(self):
        return Mapping(
            self.maps[:], (self.mirror[:] if self.mirror else None), self.from_, self.to
        )

    def append_map(self, map, mirrors=None):
        self.maps.append(map)
        self.to = len(self.maps)
        if mirrors is not None:
            self.set_mirror(len(self.maps) - 1, mirrors)

    def append_mapping(self, mapping: "Mapping"):
        i = 0
        start_size = len(self.maps)
        while i < len(mapping.maps):
            mirr = mapping.get_mirror(i)
            i += 1
            self.append_map(
                mapping.maps[i],
                (start_size + mirr) if (mirr is not None and mirr < i) else None,
            )

    def get_mirror(self, n):
        if self.mirror:
            for i in range(len(self.mirror)):
                if (self.mirror[i]) == n:
                    return self.mirror[i + (-1 if i % 2 else 1)]

    def set_mirror(self, n, m):
        if not self.mirror:
            self.mirror = []
        self.mirror.extend([n, m])

    def append_mapping_inverted(self, mapping: "Mapping"):
        i = len(mapping.maps) - 1
        total_size = len(self.maps) + len(mapping.maps)
        while i >= 0:
            mirr = mapping.get_mirror(i)
            self.append_map(
                mapping.maps[i].invert(),
                (total_size - mirr - 1) if (mirr is not None and mirr > i) else None,
            )
            i -= 1

    def invert(self):
        inverse = Mapping()
        inverse.append_mapping_inverted(self)
        return inverse

    def map(self, pos, assoc=1):
        if self.mirror:
            return self._map(pos, assoc, True)
        for i in range(self.from_, self.to):
            pos = self.maps[i].map(pos, assoc)
        return pos

    def map_result(self, pos, assoc=1):
        return self._map(pos, assoc, False)

    def _map(self, pos, assoc, simple):
        deleted = False

        i = self.from_
        while i < self.to:
            map = self.maps[i]
            result = map.map_result(pos, assoc)
            if result.recover is not None:
                corr = self.get_mirror(i)
                if corr is not None and corr > i and corr < self.to:
                    i = corr
                    pos = self.maps[corr].recover(result.recover)
                    i += 1
                    continue
            if result.deleted:
                deleted = True
            pos = result.pos
            i += 1
        return pos if simple else MapResult(pos, deleted)
