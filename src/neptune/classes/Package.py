from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Package:
    name: str
    version: str
    download_size: int
    install_size: int
    repo: str
    # Last update on the repo side not the system side
    last_update: int
    depends: Optional[list[str]] = field(default_factory=list[str])
    make_depends: Optional[list[str]] = field(default_factory=list[str])
    wanted: Optional[bool] = False

    # make it hashable but allow modification
    def __eq__(self, other : Any):
        if not isinstance(other, Package):
            return NotImplemented

        return (self.name, self.version) == (other.name, other.version)

    def __hash__(self):
        # never put wanted in here
        return hash((self.name, self.version))
