import subprocess
import sys
import os
import requests

from neptune import functions
'''
Reinstall
'''



def reinstall():
   if not len(functions.arguments) > 0:
      print("Usage: neptune-reinstall {{PACKAGES}}") 
      sys.exit(1)
   if not functions.settings.yes_mode:
      print(f"Packages to be reinstall: {" ".join(functions.arguments)}")
      confirmation=input(f"{len(functions.arguments)} packages are queued to install, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   for package in functions.arguments:
      if package not in functions.installed_packages:
         print(f'{package} is not installed!')
         sys.exit(1)
   functions.install_packages(functions.arguments, "other", reinstalling=True)
