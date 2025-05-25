from dataclasses import dataclass
from typing import Optional

@dataclass
class Package:
    name: str
    depends: list[str]
    version: str
    download_size: int
    install_size: int
    repo: str
    # Last update on the repo side not the system side
    last_update: int
    wanted: Optional[bool]


