#!/bin/python3
import sys

import yaml
import neptune.functions as functions 
from neptune.install import install
from neptune.reinstall import reinstall
from neptune.remove import remove
from neptune.sync import sync
from neptune.update import update
def parse_config():
   try:
      with open('/etc/neptune/config.yaml', 'r') as config_file:
         try:
            config= yaml.safe_load(config_file)
         except yaml.YAMLError as e:
            print(f"Error parsing yaml syntax {e}")
   except Exception as e:
      print(f"An unexpected error occured {e}")
   try:
      functions.settings.repo = config['repositories'][0]
      functions.settings.install_path = config['system-settings']['install_path']
      functions.settings.yes_mode = config['system-settings']['yes_mode_by_default']
      functions.settings.stream_chunk_size = config['system-settings']['stream_chunk_size']
   except KeyError as e:
      print(f"An unexpected value was found in {e}")

def parse_arguments():
  valid_cli_arguments = ["--y", "--no-depend"]
  cooresponding = [functions.settings.yes_mode, functions.settings.no_depend_mode]

  if len(functions.arguments) == 0 or (functions.arguments[0] not in ("install", "update", "sync", "reinstall", "remove")):
     usage="""Usage: neptune [operation] [flags] [packages (if applicable)]
           
The package manager, used to install, update, reinstall, or remove packages

   Operations:
      sync: Used to sync local cache with the repository, you need to do this before updating
      install: Used to install programs, append any and all packages that you want to install after this
      reinstall: Used to reinstall packages, append any and all packages that you want reinstalled after this
      update: Used to update the system, do NOT append any packages after this
      remove: Used to remove packages from the system
   Flags:
       --y: Temporarily disables confirmation with all operations that require one
       --no-depend: Temporarily disables dependency resolution"""
     print(usage)
     sys.exit(0)
  global operation
  operation = functions.arguments[0]
  functions.arguments.pop(0)
  for argindex in range(len(valid_cli_arguments)):
    if valid_cli_arguments[argindex] in functions.arguments:
      cooresponding[argindex] = True
      # How many packages could you possibly pass? probably fine to use remove
      functions.arguments.remove(valid_cli_arguments[argindex])
def run_operation():
   match operation:
      case "install":
         install()
      case "update":
         update()
      case "reinstall":
         reinstall()
      case "remove":
         remove()
      case "sync":
         sync()
def main():
   # also initalizes all the functions variables
   functions.check_online()
   parse_config()
   parse_arguments()
   run_operation()
