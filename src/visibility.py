from __future__ import annotations

from bisect import bisect_right


class VisibleLocations:
    """
    EU5 terra_incognita country entries appear to be encoded as:

        [start, count, start, count, ...]

    Example:

        [1, 668, 717, 4695]

    represents:

        1..668
        717..5411
    """

    def __init__(self, encoded):
        if len(encoded) % 2:
            raise ValueError(
                "Visibility list has odd number of values: "
                f"{len(encoded)}"
            )

        self.ranges = []

        for i in range(0, len(encoded), 2):
            start = int(encoded[i])
            count = int(encoded[i + 1])

            if count <= 0:
                continue

            end = start + count - 1

            self.ranges.append(
                (start, end)
            )

        self.ranges.sort()

        # Useful for fast membership tests.
        self.starts = [
            start for start, _ in self.ranges
        ]

    def __contains__(self, location_id):
        location_id = int(location_id)

        i = bisect_right(
            self.starts,
            location_id
        ) - 1

        if i < 0:
            return False

        start, end = self.ranges[i]

        return start <= location_id <= end

    def count(self):
        return sum(
            end - start + 1
            for start, end in self.ranges
        )

    def iter_ids(self):
        for start, end in self.ranges:
            yield from range(start, end + 1)

    def describe(self):
        return [
            {
                "start": start,
                "end": end,
                "count": end - start + 1,
            }
            for start, end in self.ranges
        ]
