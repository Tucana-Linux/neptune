import subprocess
import sys
import os
import requests

from neptune import functions
'''
Reinstall
'''



def reinstall():
   if len(functions.arguments) == 0:
      print("Nothing to do")
      sys.exit(0)
   if not functions.yes_mode:
      print(f"Packages to be reinstall: {" ".join(functions.arguments)}")
      confirmation=input(f"{len(functions.arguments)} packages are queued to install, would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   functions.install_packages(functions.arguments, "other")
