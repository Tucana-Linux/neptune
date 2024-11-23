#!/bin/python3
from neptune.functions import * 
from neptune.install import install
from neptune.reinstall import reinstall
from neptune.remove import remove
from neptune.sync import sync
from neptune.update import update

def parse_arguments():
  valid_cli_arguments = ["--y", "--no-depend"]
  cooresponding = [yes_mode, no_depend_mode]

  if len(arguments) == 0 or (arguments[0] not in ("install", "update", "sync", "reinstall", "remove")):
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
  operation = arguments[0]
  arguments.pop(0)
  for arg in range(len(valid_cli_arguments)):
    if valid_cli_arguments[arg] in arguments:
      cooresponding[arg] = True
      # How many packages could you possibly pass? probably fine to use remove
      arguments.remove(cooresponding[arg])
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
   check_online()
   parse_arguments()
   run_operation()
