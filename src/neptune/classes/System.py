import logging
import os
import shutil
import subprocess
import sys

from rich.console import Console, Group
from rich.live import Live
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Column
from neptune.classes.NeptuneSettings import NeptuneSettings
from neptune.classes.Package import Package
from neptune.classes.Repository import Repository
from neptune.classes.Utils import Utils


class System:
    def __init__(self):
        self.settings = NeptuneSettings()
        self.postinstalls = []
        self.utils = Utils(self.settings)

        try:
           self.installed_packages = set(open(f"{self.settings.lib_dir}/installed_package", "r").read().splitlines())
           with open(f"{self.settings.lib_dir}/versions", 'r') as file:
              self.versions = dict(line.strip().split(': ') for line in file if line.strip())
        except FileNotFoundError:
           logging.critical("Unless you are installing Tucana by-hand (in which case run sync), you have a serious problem")
           logging.critical("The installed_packages or versions file is missing, please correct")
           sys.exit(1)

    def postinst(self):
       for package in self.postinstalls:
          print(f"Running {package} post-install")
          subprocess.run(f"bash /tmp/{package}-postinst", shell=True)
          subprocess.run(f'rm -f /tmp/{package}-postinst', shell=True)
   

    def check_for_and_delete(path_to_delete: str) -> None:
       # in case more logic is needed later
       subprocess.run(f'rm -f {path_to_delete}', shell=True)

    def remove_old_files(self, package: str, new_file_list: list[str]):
       # used for update to remove old stale files
       to_remove = []
       files_old = set(open(f"{self.settings.lib_dir}/file-lists/{package}.list", "r").read().splitlines())
       to_remove += [file for file in files_old if file not in new_file_list]
       for file in to_remove:
          self.check_for_and_delete(file)

    def recalculate_system_depends(self) -> list[list[str]]:
       # duplicated function for a different purpose :( isinstance has too much of a performance penalty for my liking
       def check_if_packages_exist_return_packages(packages):
          packages_no_exist = []
          for package in packages:
             if not self.utils.check_if_package_exists(package):
                subprocess.run(f'sed -i \'/{package}/d\' {self.settings.lib_dir}/wanted_packages', shell=True)
                packages_no_exist.append(package)
          return packages_no_exist
       remove = []
       # check to see if anything currently installed is no longer avaliable
       remove.extend(check_if_packages_exist_return_packages(self.installed_packages))
       # this isn't global because sync doesn't create this file
       wanted_packages = set(open(f"{self.settings.lib_dir}/wanted_packages", "r").read().splitlines())
       logging.debug(f"Recalculating system dependencies, Current wanted packages: {wanted_packages} ")
       # no installed packages here because it's not needed check_installed is already false
       depends_of_wanted_packages = Utils.get_depends(temp_packages=wanted_packages, check_installed=False)

       install = [pkg for pkg in depends_of_wanted_packages if pkg not in self.installed_packages]
       remove += [pkg for pkg in self.installed_packages if pkg not in depends_of_wanted_packages]
       return [install, remove]

    def remove_package(self, package: str) -> None:
       # Depend checking is handled in the remove.py file, this is actually removing the program
       # therefore use this function with caution
       try:
          files = set(open(f"{self.settings.lib_dir}/file-lists/{package}.list", "r").read().splitlines())
       except FileNotFoundError:
          print(f"File list for {package} not found, skipping removal")
          return
       print(f"Removing {package}")
       for file in files:
          # os/subprocesses remove function will crash the system if it's removing something that is currently in use
          self.check_for_and_delete(f'{self.settings.install_path}/{file}')
       # Sed's are easier to understand
       # it's removed from wanted in remove.py
       subprocess.run(f"sed -i '/^{package}$/d' {self.settings.lib_dir}/installed_package" , shell=True)
       subprocess.run(f"sed -i '/^{package}:.*$/d' {self.settings.lib_dir}/versions" , shell=True)

    def remove_packages(self, packages: list[str]):
       text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
       bar_column = BarColumn(bar_width=80, table_column=Column(ratio=5))
       with Progress(text_column, bar_column, expand=True) as progress:
          remove_task = progress.add_task('[red]Removing...', total=len(packages))
          for package in packages:
             self.remove_package(package)
             progress.update(remove_task, advance=1)

    def install_files(self, package: str) -> None:
       # needed for updates & reinstalls
       os.chdir(f"{self.settings.cache_dir}/{package}")
       backup=self.utils.parse_backup_file(package)
       for root, dirs, files in os.walk(f'.'):
          for dir_name in dirs:
             folder_path = os.path.join(self.settings.install_path, os.path.join(root, dir_name).lstrip('.'))
             os.makedirs(folder_path, exist_ok=True)
          for file in files:
             if file in ('postinst', 'depends', 'depend', 'make-depend', 'make-depends', 'preinst', 'prerm', 'preupdate', 'backup', 'version'):
                continue
             file_path = os.path.join(self.settings.install_path, os.path.join(root, file).lstrip('.'))
             src_path = os.path.join(root, file)
             dest_path = os.path.join(self.settings.install_path, os.path.join(root, file).lstrip('.'))
             # TODO Implement logging Rahul Chandra <rahul@tucanalinux.org>
             if (file_path not in backup) or (not os.path.exists(file_path)):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(src_path, dest_path)
       os.chdir(self.settings.cache_dir)

    def install_package(self, package: str, repo: Repository, reinstalling: bool = False, console_line=None) -> None:
       if not os.path.exists(self.settings.cache_dir):
          os.makedirs(self.settings.cache_dir)
       os.chdir(self.settings.cache_dir)

       # we can leave the other ones blank since we are using a package
       repo.download_link("", "", package=package, console_line=console_line)

       console_line.update(f"{package} Extracting...")
       subprocess.run(f'tar -xpf {package}.tar.xz', shell=True)

       logging.info(f"Generating File List for {package}")

       file_list=self.utils.generate_file_list(package)
       if os.path.exists(f"{self.settings.lib_dir}/file-lists/{package}.list"):
          self.remove_old_files(package, file_list)

       open(f'{self.settings.lib_dir}/file-lists/{package}.list').write('\n'.join(file_list))

       console_line.update(f"{package} Installing...")
       self.install_files(package)
   
       if os.path.exists(f'{package}/postinst'):
          self.postinstalls.append(package)
          subprocess.run(f'cp {package}/postinst /tmp/{package}-postinst', shell=True)
       if not reinstalling:
          open(f'{self.settings.lib_dir}/installed_package', 'a').write(package + "\n")
          open(f'{self.settings.lib_dir}/versions', 'a').write(f"{package}: {repo.get_package_ver(package)}" + "\n")
       subprocess.run(f'rm -rf {package}', shell=True)
       subprocess.run(f'rm -f {package}.tar.xz', shell=True)

    def install_packages(self, packages: list[str], reinstalling=False):
       console = Console()
       text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
       bar_column = BarColumn(bar_width=None, table_column=Column(ratio=5))
       progress = Progress(text_column, bar_column, expand=True)
       status_lines=[]
       current_line = console.status("", refresh_per_second=10)
       task = progress.add_task("Installing", total=len(packages))
       rows = shutil.get_terminal_size().lines - 4

       def get_status_group():
            visible_lines = status_lines[-rows:] if len(status_lines) > rows else status_lines
            return Group(
                *visible_lines,  # All completed package lines
                current_line,   # Current operation line
                progress       # Progress bar at bottom
             )

       with Live(get_status_group(), refresh_per_second=10, console=console) as live:
          for package in packages:
             # TODO maybe find a way of avoiding doing this twice <rahul@tucanalinux.org>
             repo = self.utils.find_repo_with_best_version(package)
             self.install_package(package, repo, reinstalling, console_line=current_line)
             status_lines.append(rf" {package} \[[bold blue]✔[/bold blue]]")
             progress.update(task, advance=1)
             live.update(get_status_group())
       # only needed for bootstrap postinst
       if self.settings.run_postinst:
          self.postinst()

    