from pathlib import Path
import subprocess
import sys
import os
import requests
import neptune
from neptune import functions
from neptune.classes.NeptuneSettings import NeptuneSettings
from neptune.sync import sync

# This runs completely standalone from __init__ and therefore a lot of functions are repeated
# TODO fix this garbage
arguments = list(sys.argv)
arguments.pop(0)
path = ""
cache_dir = ""
lib_dir = ""
settings = NeptuneSettings()
def parse_arguments():
  valid_cli_arguments = ["--y"]

  if len(arguments) == 0:
     usage="""Usage: neptune-bootstrap [path] [flags]
   Flags:
       --y: Temporarily disables confirmation with all operations that require one
           """
     print(usage)
     sys.exit(0)
  global path
  path = arguments[0]
  arguments.pop(0)
  for arg in range(len(valid_cli_arguments)):
    if valid_cli_arguments[arg] in arguments:
      match arg:
               case 0:
                  settings.yes_mode = True
               case 1:
                  settings.no_depend_mode = True
            # How many packages could you possibly pass? probably fine to use remove
      arguments.remove(valid_cli_arguments[arg])


def create_inital_files():
   os.makedirs(cache_dir)
   os.makedirs(f'{lib_dir}/file-lists')
   os.makedirs(f'{cache_dir}/depend')
   try: 
      sha256 = requests.get(f'{settings.repo}/available-packages/sha256', allow_redirects=True)
      available_packages = requests.get(f'{settings.repo}/available-packages/packages', allow_redirects=True)
      open(f'{lib_dir}/current', 'wb').write(sha256.content)
      open(f'{cache_dir}/available-packages', 'wb').write(available_packages.content)
   except:
      print("Error retreiving files from the repository is it online?")
      sys.exit(1)
   subprocess.run(f'cp {lib_dir}/current {cache_dir}/sha256', shell=True)


def bootstrap():
   # This is a complete reimplmentation, neptune main never gets called here.
   neptune.parse_config()
   neptune.parse_repos()
   parse_arguments()
   settings.install_path = path
   settings.cache_dir = f"{path}/var/lib/neptune/cache"
   settings.lib_dir = f"{path}/var/lib/neptune/"
   if not os.listdir(path) == []:
      print("This directory is not empty!")
      sys.exit(1)
   global cache_dir
   global lib_dir
   lib_dir = f'{path}/var/lib/neptune'
   cache_dir = f'{lib_dir}/cache'
   create_inital_files()
   print("Syncing")

   sync()

   print("Getting dependencies")
   packages=functions.get_depends(["base"], check_installed=False)
   if not functions.settings.yes_mode:
      print(f"Packages to install: {" ".join(packages)}") 
      confirmation=input(f"You are about to bootstrap {path}, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   functions.install_packages(packages)

