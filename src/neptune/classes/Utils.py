import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional

from packaging.version import Version
from neptune.classes.Repository import Repository
from neptune.classes.NeptuneSettings import NeptuneSettings
from neptune.classes.Package import Package


class Utils:

    '''
    Utilities that should be able to be used agnostic to the system. 
    Some utilities optionally can take elements from the system,
    like get_depends with installed_packages, but for the most part
    it just needs settings to be set properly.
    ''' 

    def __init__(self, settings: NeptuneSettings):
        self.settings = settings

    def version_normalizer(self, version:str) -> str:
       #version = re.sub(r"^[^\d]+", "", version)
       #version = re.sub(r"[a-zA-Z]", ".", version)
       #version = re.sub(r"[a-zA-Z]", "", version)
       # Replace underscores and hyphens with dots
       #version = version.replace("_", ".").replace("-", ".")
       # 1. Remove leading non-digit characters
       version = re.sub(r'^[^\d]+', '', version)
       # 2. Replace underscores and hyphens with dots
       version = re.sub(r'[_-]', '.', version)
       # 3. Remove any remaining letters
       version = re.sub(r'[a-zA-Z]', '', version)
       return version 

    def parse_backup_file(self, package: str) -> list[str]:
       backup=[]
       os.chdir(f'{self.settings.cache_dir}/{package}')
       if os.path.isfile('./backup'):
          try:
             with open('backup', 'r') as backup_file:
                backup = [os.path.join(self.settings.install_path, line.rstrip()) for line in backup_file]
          except Exception as e:
             logging.error(f"Error reading from backup file error {e}")
       return backup
    
    def generate_file_list(self, package: str) -> list[str]:
        os.chdir(f'{self.settings.cache_dir}/{package}')

        files = [f"/{p}" for p in Path('.').rglob('*') if p.is_file() or p.is_symlink()]
        backup = self.parse_backup_file(package)
        if backup:
            files = [f for f in files if all(b not in f for b in backup)]

        os.chdir(self.settings.cache_dir)
        return files


    def find_repo_with_best_version(self, package: str) -> Repository:
       latest_ver = Version('0')
       # by the fact that check_package_exists will always be run before this, there will **should** always be a best repo
       best_repo = None
       for _, repo in self.settings.repositories.items():
          if not repo.check_if_package_exists(package):
            continue
          version = Version(self.version_normalizer(repo.get_package_ver(package)))
          if version > latest_ver:
             latest_ver = version
             best_repo = repo
       # just in case
       if best_repo == None:
          logging.critical(f"Could not find a good repo for {package} even though it exists, THIS IS A BUG, please report to https://github.com/Tucana-Linux/issues")
          sys.exit(1)
       return best_repo

    # TODO Fix bug here #13
    def check_if_package_exists(self, package: str) -> bool:
       for _, repo in self.settings.repositories.items():
          if repo.check_if_package_exists(package):
             return True
       return False

    def check_if_packages_exist(self, packages: list[str]) -> bool:
       for package in packages:
          logging.debug(f"checking existence of {package}")
          if not self.check_if_package_exists(package):
             logging.warning(f"{package} not found")
             return False
       return True
    
    def get_depends(self, temp_packages: list[str], check_installed: bool, installed_packages: Optional[set[str]] = None,  processing_set: Optional[set[str]] = None):
       # This one should start none
       if processing_set == None:
          processing_set = set()
       # this one may be null (recalculating system depends)
       if installed_packages == None:
          installed_packages = set()

       for package in temp_packages:
          if (not package in processing_set) and (not check_installed or not (package in installed_packages)):
             processing_set.add(package)
             try:
                depends=[]
                repo: Repository = self.find_repo_with_best_version(package).name
                with open(f'{self.settings.cache_dir}/repos/{repo}/depend/depend-{package}', 'r') as depend_file:
                   depends = depend_file.read().split()
             except FileNotFoundError:
                logging.warning(f"{package} depends file NOT found, something is SERIOUSLY WRONG")
                continue
             # Validate then recurse
             logging.debug(f"{package} has depends {depends}")
             logging.debug(f"Current packages set: {processing_set}")
             if not self.check_if_packages_exist(depends):
                logging.critical(f"Error: Dependencies for {package} could not be found: depends: {depends}, this is a repository bug, please report to your repo admin. The unavailable package in question is the one shown in the line above this message")
                sys.exit(1)
             self.get_depends(depends, check_installed, processing_set=processing_set, installed_packages=installed_packages)
       packages = [*processing_set] 
       return packages

    def check_for_updates(self, installed_packages : set[str], versions: dict[str, str]) -> list[str]:
       updates = []

       for package in installed_packages:
          # ignore unavailable packages
          if not self.check_if_packages_exist([package]):
             continue
          best_repo = self.find_repo_with_best_version(package)
          best_ver = best_repo.get_package_ver(package)
          logging.debug(f"Best version for {package} is {best_ver} from {best_repo.name}")
          logging.debug(f"Current version of {package} is {versions[package]}")
          if Version(self.version_normalizer(best_ver)) > Version(self.version_normalizer(versions[package])):
             updates.append(package)
   
       return updates

    def check_if_packages_exist_return_packages(self, packages):
       packages_no_exist = []
       for package in packages:
          if not self.check_if_package_exists(package):
             subprocess.run(f'sed -i \'/{package}/d\' {self.settings.lib_dir}/wanted_packages', shell=True)
             packages_no_exist.append(package)
       return packages_no_exist

    def recalculate_system_depends(self, wanted_packages: set[str], installed_packages: set[str]) -> list[list[str]]:
       remove = []
       # check to see if anything currently installed is no longer avaliable
       remove.extend(self.check_if_packages_exist_return_packages(installed_packages))
       logging.debug(f"Recalculating system dependencies, Current wanted packages: {wanted_packages} ")
       # no installed packages here because it's not needed check_installed is already false
       depends_of_wanted_packages = self.get_depends(temp_packages=wanted_packages, check_installed=False)

       install = [pkg for pkg in depends_of_wanted_packages if pkg not in installed_packages]
       remove += [pkg for pkg in installed_packages if pkg not in depends_of_wanted_packages]
       logging.debug(f"Recalculator says to remove {remove}")
       logging.debug(f"Recalculator says to install {install}")
       return [install, remove]