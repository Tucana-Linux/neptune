from neptune.classes.Repository import Repository


class Package:
    # both sizes are in KB
    def __init__(self, name: str, repo: Repository, depends: list[str], version: str, install_size: int, download_size: int):
        self.name = name
        self.repo = repo 
        self.depends = depends
        self.version = version
        self.install_size = install_size
        self.download_size = download_size
