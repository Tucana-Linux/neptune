import subprocess
import sys
import os
import requests
import functions

def install():
   print("Getting dependencies")
   functions.get_depends(functions.arguments)
   if len(functions.packages) == 0:
      print("Nothing to do all packages are installed")
      sys.exit()

   if not functions.yes_mode:
      print(f"Packages to install: {" ".join(functions.packages)}") 
      confirmation=input(f"{len(functions.packages)} packages are queued to install, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   functions.install_packages(functions.packages, "install")

   for package in functions.arguments:
      with open(f'{functions.install_path}/etc/wanted_packages', 'a') as wanted_packages:
         # you cannot upgrade base
         if package != "base":
            wanted_packages.write(package + "\n")