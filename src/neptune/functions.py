#!/bin/python3
import logging
from packaging.version import Version
import shutil
import subprocess
import sys
import os
import requests
from rich.table import Column
from rich.console import Console, Group
from rich.panel import Panel
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn
from neptune.classes.NeptuneSettings import NeptuneSettings


if os.geteuid() != 0:
   logging.error("This package manager must be run as root")
   sys.exit()

# Get terminal rows to know how many packages to print at once
rows, _ = shutil.get_terminal_size()

settings = NeptuneSettings()
# ANSI Codes
move_up_one='\033[A'
return_b = '\r'
clear='\033[K'
# Global vars
#lib_dir = f'{settings.install_path}/var/lib/neptune'
#cache_dir = f'{settings.install_path}/{lib_dir}/cache'
postinstalls = []
packages = []
packages_set = set()
operation = ""

# needs to be down here because it repository relies on cache_dir, it could be above but this makes it more obvious
try:
   installed_packages = set(open(f"{settings.lib_dir}/installed_package", "r").read().splitlines())
   with open(f"{settings.lib_dir}/versions", 'r') as file:
      versions = dict(line.strip().split(': ') for line in file if line.strip())
except FileNotFoundError:
   logging.critical("Unless you are installing Tucana by-hand (in which case run sync), you have a serious problem")
   logging.critical("The installed_packages or versions file is missing, please correct")
   sys.exit(1)


# Argument stuff
no_depend_mode = False
arguments = list(sys.argv)
arguments.pop(0)

'''
Universal Functions
'''


def generate_file_list(package):
    os.chdir(f'{settings.cache_dir}/{package}')
    # This is a bash oneliner, I know it isn't ideal but it's easier to read than the python alternative
    subprocess.run(f'find * -type f | sed \'s|^|/|g\' > {settings.lib_dir}/file-lists/{package}.list', shell=True)
    # Remove the files that need to be backed up from the file-list so that they aren't removed
    backup=parse_backup_file(package)
    if not len(backup) == 0:
       for file in backup:
          subprocess.run(f'sed -i "\\@{file}@d" {settings.lib_dir}/file-lists/{package}.list', shell=True)
    os.chdir(settings.cache_dir)

# Any error that may be ignored should use this function, otherwise exit within.

def postinst():
   for package in postinstalls:
      print(f"Running {package} post-install")
      subprocess.run(f"bash /tmp/{package}-postinst", shell=True)
      subprocess.run(f'rm -f /tmp/{package}-postinst', shell=True)
   
def check_for_and_delete(path_to_delete):
   # in case more logic is needed later
   subprocess.run(f'rm -f {path_to_delete}', shell=True)

def parse_backup_file(package):
   backup=[]
   os.chdir(f'{settings.cache_dir}/{package}')
   if os.path.isfile('./backup'):
      try:
         with open('backup', 'r') as backup_file:
            backup = [os.path.join(settings.install_path, line.rstrip()) for line in backup_file]
      except Exception as e:
         logging.error(f"Error reading from backup file error {e}")
   return backup

def copy_files(package):
   # doesn't check for backup because it is only used on first install
   try:
      subprocess.run(f'cp -rp {package}/* {settings.install_path}', shell=True)
   except Exception as e:
        logging.error(f"Error could not copy files exception {e}")
   for i in ['depends', 'depend', 'make-depend', 'make-depends', 'postinst', 'preinst', 'prerm', 'preupdate', 'backup']:
      check_for_and_delete(f'{settings.install_path}/{i}')

def update_files(package):
   # needed for updates & reinstalls
   backup=parse_backup_file(package)
   for root, dirs, files in os.walk(f'.'):
      for dir_name in dirs:
         folder_path = os.path.join(settings.install_path, os.path.join(root, dir_name).lstrip('.'))
         os.makedirs(folder_path, exist_ok=True)
      for file in files:
         if file in ('postinst', 'depends'):
            continue
         file_path = os.path.join(settings.install_path, os.path.join(root, file).lstrip('.'))
         # TODO Implement logging Rahul Chandra <rahul@tucanalinux.org>
         if file_path not in backup:
            subprocess.run(f'mv {os.path.join(root, file)} {file_path}', shell=True)
   os.chdir(settings.cache_dir)

def find_repo_with_best_version(package):
   latest_ver = Version('0.0.0.0.0')
   # by the fact that check_package_exists will always be run before this, there will **should** always be a best repo
   best_repo = ""
   for repo in settings.repositories:
      if not repo.check_if_package_exists(package):
        continue
      version = Version(repo.get_package_ver(package))
      if version > latest_ver:
         latest_ver = version
         best_repo = repo
   # just in case
   if repo == "":
      logging.critical(f"Could not find a good repo for {package} even though it exists, THIS IS A BUG, please report to https://github.com/Tucana-Linux/issues")
   return best_repo
      

def install_package(package, repo, operation, reinstalling=False, console_line=None):
   if not os.path.exists(settings.cache_dir):
      os.makedirs(settings.cache_dir)
   os.chdir(settings.cache_dir)

   # we can leave the other one's blank since we are using a package
   repo.download_link("", "", package=package, console_line=console_line)

   console_line.update(f"{package} Extracting...")
   subprocess.run(f'tar -xpf {package}.tar.xz', shell=True)

   logging.info(f"Generating File List for {package}")
   generate_file_list(package)

   console_line.update(f"{package} Installing...")
   match operation:
      case "install":
         copy_files(package)
      case "other":
         update_files(package)
   
   if os.path.exists(f'{package}/postinst'):
      postinstalls.append(package)
      subprocess.run(f'cp {package}/postinst /tmp/{package}-postinst', shell=True)
   if not reinstalling:
      open(f'{settings.lib_dir}/installed_package', 'a').write(package + "\n")
      open(f'{settings.lib_dir}/version', 'a').write(f"{package}: {repo.get_package_ver(package)}" + "\n")
   subprocess.run(f'rm -rf {package}', shell=True)
   subprocess.run(f'rm -f {package}.tar.xz', shell=True)

def install_packages(packages, operation, reinstalling=False):
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
         repo = find_repo_with_best_version(package)
         install_package(package, repo, operation, reinstalling, console_line=current_line)
         status_lines.append(rf" {package} \[[bold blue]✔[/bold blue]]")
         progress.update(task, advance=1)
         live.update(get_status_group())
   postinst()

def check_if_packages_exist(packages):
   for package in packages:
      for repo in settings.repositories:
         if repo.check_if_package_exists(package):
            return True
      logging.error(f"{package} not found")
      sys.exit(1)
      

def check_if_package_installed(package, check):
   # If check is false it will always return false, this is to account for the depend recalculation during remove
   if not check:
      return False
   return package in installed_packages

def get_depends(temp_packages, check_installed):
   if len(temp_packages) == 0:
      packages = [*packages_set]
      return [*packages_set]
   for package in temp_packages:
      # the check_installed is to avoid mutliple functions or ifs, it just makes check_if_package_installed return false if it is false.
      if not (package in packages_set or check_if_package_installed(package, check_installed)):
         packages_set.add(package)
         try:
            depends=[]
            repo = find_repo_with_best_version(package).name
            with open(f'{settings.cache_dir}/{repo}/depend/depend-{package}', 'r') as depend_file:
               depends = depend_file.read().split()
         except FileNotFoundError:
            logging.warning(f"{package} depends file NOT found, something is SERIOUSLY WRONG")
            continue
         # Validate then recurse
         check_if_packages_exist(depends)
         get_depends(depends, check_installed)
   return packages_set


def recalculate_system_depends():
   # duplicated function for a different purpose :( isinstance has too much of a performance penalty for my liking
   def check_if_packages_exist(packages):
      packages_no_exist = []
      for package in packages:
         for repo in settings.repositories:
            if repo.check_if_package_exists(package):
               return True
         print(f"{package} not found")
         subprocess.run(f'sed -i \'/{package}/d\' {settings.lib_dir}/wanted_packages', shell=True)
         packages_no_exist.append(package)
      return packages_no_exist
   remove = []
   # check to see if anything currently installed is no longer avaliable
   remove.extend(check_if_packages_exist(installed_packages) )
   # this isn't global because sync doesn't create this file
   wanted_packages = set(open(f"{settings.lib_dir}/wanted_packages", "r").read().splitlines())
   depends_of_wanted_packages = get_depends(wanted_packages, check_installed=False)

   install = [pkg for pkg in depends_of_wanted_packages if pkg not in installed_packages]
   remove += [pkg for pkg in installed_packages if pkg not in depends_of_wanted_packages]
   return [install, remove]

def remove_package(package):
   # Depend checking is handled in the remove.py file, this is actually removing the program
   # therefore use this function with caution
   try:
      files = set(open(f"{settings.lib_dir}/file-lists/{package}.list", "r").read().splitlines())
   except FileNotFoundError:
      print(f"File list for {package} not found, skipping removal")
      return
   print(f"Removing {package}")
   for file in files:
      # os/subprocesses remove function will crash the system if it's removing something that is currently in use
      check_for_and_delete(f'{settings.install_path}/{file}')
   # Sed's are easier to understand
   # it's removed from wanted in remove.py
   subprocess.run(f"sed -i '/^{package}$/d' {settings.lib_dir}/installed_package" , shell=True)
   subprocess.run(f"sed -i '/^{package}:.*$/d' {settings.lib_dir}/version" , shell=True)

def remove_packages(packages):
   text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
   bar_column = BarColumn(bar_width=80, table_column=Column(ratio=5))
   with Progress(text_column, bar_column, expand=True) as progress:
      remove_task = progress.add_task('[red]Removing...', total=len(packages))
      for package in packages:
         remove_package(package)
         progress.update(remove_task, advance=1)




