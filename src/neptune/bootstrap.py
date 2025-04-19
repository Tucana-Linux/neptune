from pathlib import Path
import subprocess
import sys
import os
import neptune
from neptune import functions, sync
from neptune.classes.NeptuneSettings import NeptuneSettings

# This runs completely standalone from __init__ and therefore a lot of functions are repeated
# TODO fix this garbage
arguments = list(sys.argv)
arguments.pop(0)
settings = NeptuneSettings()
path=""
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
   os.makedirs(settings.cache_dir)
   os.makedirs(f'{settings.lib_dir}/file-lists')
   os.makedirs(f'{settings.cache_dir}/depend')
   subprocess.run(f"touch {settings.lib_dir}/versions", shell=True)
   subprocess.run(f"touch {settings.lib_dir}/installed_package", shell=True)


def bootstrap():
   neptune.parse_config()
   neptune.parse_repos()
   parse_arguments()
   settings.install_path = path
   settings.run_postinst = False
   settings.cache_dir = f"{path}/var/lib/neptune/cache"
   settings.lib_dir = f"{path}/var/lib/neptune/"
   if not os.listdir(path) == []:
      print("This directory is not empty!")
      sys.exit(1)
   create_inital_files()
   # This sync would sync the system about to be bootstrapped which isn't advisable.
   sync()

   print("Getting dependencies")
   packages=functions.get_depends(["base"], check_installed=False)
   if not functions.settings.yes_mode:
      print(f"Packages to install: {" ".join(packages)}") 
      confirmation=input(f"You are about to bootstrap {path}, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   functions.install_packages(packages, "install")

