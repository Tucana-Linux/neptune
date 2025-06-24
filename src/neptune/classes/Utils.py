import logging
import os
from pathlib import Path
import re
import sys
from typing import Optional

from packaging.version import Version
from neptune.classes.Package import Package
from neptune.classes.Repository import Repository
from neptune.classes.NeptuneSettings import NeptuneSettings


class Utils:
    """
    Utilities that should be able to be used agnostic to the system.
    Some utilities optionally can take elements from the system,
    like get_depends with installed_packages, but for the most part
    it just needs settings to be set properly.
    """

    def __init__(self, settings: NeptuneSettings):
        self.settings = settings

    def version_normalizer(self, version: str) -> str:
        # version = re.sub(r"^[^\d]+", "", version)
        # version = re.sub(r"[a-zA-Z]", ".", version)
        # version = re.sub(r"[a-zA-Z]", "", version)
        # Replace underscores and hyphens with dots
        # version = version.replace("_", ".").replace("-", ".")
        # 1. Remove leading non-digit characters
        version = re.sub(r"^[^\d]+", "", version)
        # 2. Replace underscores and hyphens with dots
        version = re.sub(r"[_-]", ".", version)
        # 3. Remove any remaining letters
        version = re.sub(r"[a-zA-Z]", "", version)
        return version

    def parse_backup_file(self, package: str) -> list[str]:
        backup = []
        os.chdir(f"{self.settings.cache_dir}/{package}")
        if os.path.isfile("./backup"):
            try:
                with open("backup", "r") as backup_file:
                    backup = [
                        os.path.join(self.settings.install_path, line.rstrip())
                        for line in backup_file
                    ]
            except Exception as e:
                logging.error(f"Error reading from backup file error {e}")
        return backup
    
    
    def try_remove_folder(self, folder: str) -> None:
        """
        Attempt to remove empty folders recursively
        """
        try:
            logging.debug(f"Attempting to remove folder {folder}")
            os.rmdir(folder)
            self.try_remove_folder(os.path.dirname(folder))
        except OSError:
            logging.debug(f"Recursion ended (did not delete) at {folder}")
            pass

    def generate_file_list(self, package: str) -> list[str]:
        os.chdir(f"{self.settings.cache_dir}/{package}")
        # python abracadabra
        files = [f"/{p}" for p in Path(".").rglob("*") if p.is_file() or p.is_symlink()]
        backup = self.parse_backup_file(package)
        if backup:
            files = [f for f in files if all(b not in f for b in backup)]

        os.chdir(self.settings.cache_dir)
        return files

    def find_repo_with_best_version(self, package: str) -> Repository:
        latest_ver = Version("0")
        # by the fact that check_package_exists will always be run before this, there will **should** always be a best repo
        best_repo = None
        for _, repo in self.settings.repositories.items():
            if not repo.check_if_package_exists(package):
                continue
            version = Version(
                self.version_normalizer(repo.get_package(package).version)
            )
            if version > latest_ver:
                latest_ver = version
                best_repo = repo
        # just in case
        if best_repo is None:
            logging.critical(
                f"Could not find a good repo for {package}, THIS IS A BUG, please report to https://github.com/Tucana-Linux/issues"
            )
            raise FileNotFoundError
        return best_repo

    # TODO Fix bug here #13
    def check_if_package_exists(self, package: str) -> bool:
        for _, repo in self.settings.repositories.items():
            if repo.check_if_package_exists(package):
                return True
        return False

    def check_if_packages_exist(self, packages: set[str]) -> bool:
        for package in packages:
            logging.debug(f"checking existence of {package}")
            if not self.check_if_package_exists(package):
                logging.warning(f"{package} not found")
                return False
        return True

    def get_depends(
        self,
        temp_packages: set[str],
        system_packages: Optional[dict[str, Package]] = None,
        processing_dict: Optional[dict[str, Package]] = None,
    ) -> list[Package]:
        # This one should start none
        if processing_dict is None:
            processing_dict = {}
        # this one may be null (recalculating system depends)
        if system_packages is None:
            system_packages = {}

        for package_name in temp_packages:
            if (package_name not in processing_dict) and (
                package_name not in system_packages
            ):
                repo: Repository = self.find_repo_with_best_version(package_name)
                package = repo.get_package(package_name)
                depends: set[str] = set(package.depends or [])
                # Validate then recurse
                logging.debug(f"{package_name} has depends {depends}")
                logging.debug(f"Current packages set: {processing_dict}")
                if not self.check_if_packages_exist(depends):
                    logging.critical(
                        f"Error: Dependencies for {package_name} could not be found: depends: {depends}, this is a repository bug, please report to your repo admin. The unavailable package in question is the one shown in the line above this message"
                    )
                    sys.exit(1)
                processing_dict[package_name] = package
                self.get_depends(
                    depends,
                    processing_dict=processing_dict,
                    system_packages=system_packages,
                )
        packages = list(processing_dict.values())
        return packages
    
    def reverse_remove_depends(
        self, 
        packages_to_remove: set[str], 
        system_packages: dict[str, Package], 
        processing_set: Optional[set[str]] = None
    ) -> set[str]:
        """
        Alloes non-wanted packages to be removed by calculating what
        packages depend on them recursively
        Returns set of packages to remove
        """
        if processing_set is None:
            processing_set = set()
        depends : set[str] = set() 
        for package in packages_to_remove:
            processing_set.add(package)
            for name, test_package_object in system_packages.items():
                if package in (test_package_object.depends or []):
                    depends.add(name)
        new_depends = depends - processing_set         
        if new_depends: 
            self.reverse_remove_depends(new_depends, 
                                        system_packages=system_packages,
                                        processing_set=processing_set)
        return processing_set
        
    def check_for_updates(self, system_packages: dict[str, Package]) -> list[Package]:
        updates: list[Package] = []

        for package in system_packages.values():
            # ignore unavailable packages
            if not self.check_if_package_exists(package.name):
                continue
            best_repo: Repository = self.find_repo_with_best_version(package.name)
            best_package: Package = best_repo.get_package(package.name)
            logging.debug(
                f"Best version for {package} is {best_package.version} from {best_repo.name}"
            )
            logging.debug(f"Current version of {package.name} is {package.version}")
            if Version(self.version_normalizer(best_package.version)) > Version(
                self.version_normalizer(package.version)
            ):
                updates.append(best_package)

        return updates

    def check_if_packages_exist_return_packages(
        self, system_packages: dict[str, Package]
    ) -> list[str]:
        packages_no_exist: list[str] = []
        for package in system_packages.keys():
            if not self.check_if_package_exists(package):
                packages_no_exist.append(package)
        return packages_no_exist

    def recalculate_system_depends(
        self, system_packages: dict[str, Package]
    ) -> tuple[list[Package], list[str]]:

        # Remove only uses strings internally so only use strongs here
        remove: list[str] = []
        # check to see if anything currently installed is no longer avaliable
        remove.extend(self.check_if_packages_exist_return_packages(system_packages))
        wanted_package_names: set[str] = {
            package.name for package in system_packages.values() if package.wanted and package not in remove
        }
        logging.debug(
            f"Recalculating system dependencies, Current wanted packages: {wanted_package_names} "
        )
        # no installed packages here because it's not needed check_installed is already false
        depends_of_wanted_packages: list[Package] = self.get_depends(
            temp_packages=wanted_package_names
        )
        logging.debug(f"Depends of wanted packages are {depends_of_wanted_packages}")

        install = [
            pkg
            for pkg in depends_of_wanted_packages
            if pkg.name not in system_packages.keys()
        ]
        remove += [
            pkg.name
            for pkg in system_packages.values()
            if pkg.name not in {p.name for p in depends_of_wanted_packages}
        ]
        logging.debug(f"Recalculator says to remove {remove}")
        logging.debug(f"Recalculator says to install {install}")
        return (install, remove)
