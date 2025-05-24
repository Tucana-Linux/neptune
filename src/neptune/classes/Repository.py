from __future__ import annotations
from typing import TYPE_CHECKING

import yaml

from neptune.classes import Package

if TYPE_CHECKING:
    from neptune.classes.NeptuneSettings import NeptuneSettings
from rich.status import Status
import os
import logging
import subprocess
import sys

import requests

# only for the type decl


class Repository:
    def __init__(self, name: str, url: str, settings: NeptuneSettings):
        self.name: str = name
        self.url: str = url
        # type decl causes circular dependency # TODO fix this
        self.settings = settings
        if not (len(self.name) >= 1 and len(self.url) >= 1):
            logging.critical("Configuration error with repos")
            sys.exit(1)
        self.packages = {}
        try:
            with open(f"{self.settngs.cache_dir}/repos/{self.name}/system-packages.yaml", "r") as f:
                try:
                    raw_data = yaml.safe_load(f)
                    self.packages = {name: Package(**metadata) for name, metadata in raw_data.items()}
                except yaml.YAMLError as e:
                    logging.critical(f"Repo {self.name}: YAML syntax error: {e}")
                except TypeError as e:
                    logging.critical(f"Repo {self.name}: Data structure mismatch: {e}") 
        except:
            logging.warning(f"{self.name} @ {self.url} has not been initalized")

    def check_connection(self):
        try:
            check_file = requests.head(f"{self.url}/available-packages/versions")
            if check_file.status_code != requests.codes.ok:
                logging.warning(
                    f"{self.name} This does not seem to be a Tucana repo server"
                )
                subprocess.run(
                    f"rm -rf {self.settings.cache_dir}/repos/{self.name}/", shell=True
                )
                self.__init__(self.name, self.url, self.settings)
                return False
        except requests.RequestException as e:
            logging.warning(f"Error connecting to repo {self.name}: {e}")
            subprocess.run(
                f"rm -rf {self.settings.cache_dir}/repos/{self.name}/", shell=True
            )
            self.__init__(self.name, self.url, self.settings)
            return False
        return True

    # link_path and package are mutally exclusive
    # link path is a relative path
    def download_link(
        self,
        link_path: str,
        output_path: str,
        package: str = "",
        console_line: Status | None = None,
    ) -> None:  # type: ignore
        def make_progress_bar(progress: float, total: float, width: int = 20):
            filled_length = int(width * progress / total)
            # i love you python string concatonation
            bar = "#" * filled_length + " " * (width - filled_length)
            percent = progress / total * 100
            return rf"\[{bar}] {percent:.1f}%"

        if package != "":
            link = f"{self.url}/packages/{package}.tar.xz"
            output_path = f"{self.settings.cache_dir}/{package}.tar.xz"
        else:
            link = f"{self.url}/{link_path}"

        try:
            download = requests.get(link, stream=True)
            downloaded_progress = 0

            with open(output_path, "wb") as file:
                # performance so you don't check this on every chunk
                if console_line is not None:
                    for chunk in download.iter_content(
                        chunk_size=self.settings.stream_chunk_size
                    ):
                        downloaded_progress += len(chunk)
                        bar = make_progress_bar(
                            downloaded_progress,
                            int(download.headers.get("content-length", 0)),
                        )
                        console_line.update(f"{package} Downloading {bar}")
                        file.write(chunk)
                else:
                    for chunk in download.iter_content(
                        chunk_size=self.settings.stream_chunk_size
                    ):
                        file.write(chunk)
                    # progress.update(download_task, advance=len(chunk))
        except requests.RequestException as e:
            # TODO Fix for progress bars <rahul@tucanalinux.org>
            logging.warning(
                f"Failed to download {link}, you have likely lost internet, error: {e}"
            )
            subprocess.run(f"rm -f {output_path}")

    def sync(self):
        # circular import?
        print(f"Syncing {self.name} at {self.url}")
        if not self.check_connection():
            return

        if not os.path.exists(path=f"{self.settings.cache_dir}/repos/{self.name}/"):
            logging.info(f"Creating {self.name} cache directory")
            os.makedirs(f"{self.settings.cache_dir}/repos/{self.name}/depend")
        logging.info(f"{self.name}: Getting Available Packages")
        self.download_link(
            f"available-packages/packages",
            f"{self.settings.cache_dir}/repos/{self.name}/available-packages",
        )

        logging.info(f"{self.name}: Getting dependency files")
        self.download_link(
            f"depend/depends.tar.xz",
            f"{self.settings.cache_dir}/repos/{self.name}/depend/depends.tar.xz",
        )
        os.chdir(f"{self.settings.cache_dir}/repos/{self.name}/depend")
        subprocess.run("tar -xf depends.tar.xz", shell=True)

        logging.info(f"{self.name}: Getting meta info")
        # self.download_link(f"available-packages/sha256", f'{self.settings.cache_dir}/repos/{self.name}/sha256')
        self.download_link(
            f"available-packages/versions",
            f"{self.settings.cache_dir}/repos/{self.name}/versions",
        )
        # reinit
        self.__init__(self.name, self.url, self.settings)

    def check_if_package_exists(self, package: str) -> bool:
        return package in self.packages

    # Precondition, a package that exists in this repo
    def get_package(self, package_name: str) -> str:
        return self.packages[package_name]
