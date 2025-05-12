from dataclasses import dataclass, field
from neptune.classes.Repository import Repository


class Package:
    depends: list[str]
    version: str
    download_size: int
    install_size: int
    repo: str
