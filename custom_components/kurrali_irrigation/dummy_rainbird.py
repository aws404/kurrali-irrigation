"""A dummy controller for local testing"""
from pyrainbird.async_client import AsyncRainbirdController
from pyrainbird.data import AvailableStations, ModelAndVersion, States

class DummyStates(States):
    """A dummy state holder"""

    def __init__(self, states: list[bool]):
        super().__init__("0000")
        self.dummy_states = states
        self.count = len(states)

    def active(self, number):
        return self.dummy_states[number - 1]


class DummyController(AsyncRainbirdController):
    """A dummy controller for local testing"""

    def __init__(self):
        super().__init__(None)
        self.model_and_version = ModelAndVersion(7, 1, 1)
        self.stations = AvailableStations("0000")
        self.stations.stations = DummyStates([True, True, True, True])
        self.active = DummyStates([False, False, False, False])

    async def get_model_and_version(self) -> ModelAndVersion:
        return self.model_and_version

    async def get_available_stations(self, page=...) -> AvailableStations:
        return self.stations

    async def get_zone_states(self, page=...) -> States:
        return self.active

    async def get_serial_number(self) -> str:
        return "dummytest"

    async def irrigate_zone(self, zone: int, minutes: int) -> None:
        for i in range(self.active.count):
            self.active.dummy_states[i] = False

        self.active.dummy_states[zone - 1] = True

        return None
