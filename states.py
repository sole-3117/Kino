from enum import Enum, auto

class AddMovie(Enum):
    VIDEO     = auto()
    TITLE     = auto()
    QUALITY   = auto()
    YEAR      = auto()
    LANGUAGE  = auto()
    RATING    = auto()
    CODE      = auto()

class SubscriptionCheck(Enum):
    PERIOD    = auto()
    CHECK     = auto()
