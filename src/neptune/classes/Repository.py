from __future__ import annotations
from typing import TYPE_CHECKING

import yaml
from neptune.classes.Package import Package

if TYPE_CHECKING:
    from neptune.classes.NeptuneSettings import NeptuneSettings
from rich.status import Status
import os
import logging
import subprocess
import sys

import requests


class Repository:
    def __init__(self, name: str, url: str, settings: NeptuneSettings):
        self.name: str = name
        self.url: str = url
        # type decl causes circular dependency # TODO fix this
        self.settings: NeptuneSettings = settings
        if not (len(self.name) >= 1 and len(self.url) >= 1):
            logging.critical("Configuration error with repos")
            sys.exit(1)
        self.packages = {}
        try:
            with open(
                f"{self.settings.cache_dir}/repos/{self.name}/packages.yaml", "r"
            ) as f:
                try:
                    raw_data = yaml.load(f, Loader=yaml.CSafeLoader)
                    self.packages = {
                        package_name: Package(
                            **metadata, repo=self.name, name=package_name
                        )
                        for package_name, metadata in raw_data.items()
                    }
                    logging.info(
                        f"Repo {self.name} Packages available: {self.packages.keys()}"
                    )
                except yaml.YAMLError as e:
                    logging.critical(f"Repo {self.name}: YAML syntax error: {e}")
                    sys.exit(1)
                except TypeError as e:
                    logging.critical(f"Repo {self.name}: Data structure mismatch: {e}")
                    sys.exit(1)
        except Exception:
            logging.warning(f"{self.name} @ {self.url} has not been initalized")

    def check_connection(self):
        try:
            check_file = requests.head(f"{self.url}/available-packages/packages.yaml")
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
            os.makedirs(f"{self.settings.cache_dir}/repos/{self.name}")
        logging.info(f"{self.name}: Getting Available Packages")
        self.download_link(
            "available-packages/packages.yaml",
            f"{self.settings.cache_dir}/repos/{self.name}/packages.yaml",
        )

        # reinit
        self.__init__(self.name, self.url, self.settings)

    def check_if_package_exists(self, package: str) -> bool:
        return package in self.packages

    # Precondition, a package that exists in this repo
    def get_package(self, package_name: str) -> Package:
        return self.packages[package_name]
