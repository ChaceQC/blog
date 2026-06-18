from typing import TypeGuard, final


@final
class UnsetType:
    __slots__ = ()

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType()


def is_set[T](value: T | UnsetType) -> TypeGuard[T]:
    return not isinstance(value, UnsetType)
