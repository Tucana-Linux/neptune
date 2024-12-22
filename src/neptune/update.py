import subprocess
import sys
import os
import requests

from neptune import functions
'''
Update Block
'''
def check_for_updates():
   # This is almost directly refactored from mercury
   diff_command = subprocess.run(f"diff {functions.cache_dir}/current {functions.cache_dir}/sha256", shell=True, capture_output=True, text=True)
   # Cursed python array syntax, removes .tar.xz from packages and checks the output of diff
   # to see which ones are different
   updates = [
      line.split()[-1].replace('.tar.xz', '')
      for line in diff_command.stdout.splitlines()
      if line.startswith('>')
   ]
   updates_relevant_to_system = [package for package in updates if package in functions.installed_packages]
   return updates_relevant_to_system

def update():
   updates = check_for_updates()
   recalculated_depends = functions.recalculate_system_depends()
   install = recalculated_depends[0]
   remove = recalculated_depends[1]
   
   if len(updates) == 0:
      print("No updates found, try to sync")
      sys.exit(0)
   if not functions.settings.yes_mode:
      print(f"Packages to be updated: {" ".join(updates)}")
      if len(install) > 0:
         print(f'Packages to be installed: {" ".join(install)}')
      if len(remove) > 0:
         print(f'Packages to be REMOVED: {" ".join(remove)}')
      confirmation=input(f"Would you like to continue? [Y/n] ")
      if not (confirmation=="y" or confirmation=="" or confirmation == "Y"):
         print("Aborting")
         sys.exit(0)
   if len(install) > 0:
    functions.install_packages(install, "install")
   # Remove before updating
   functions.remove_packages(updates)
   functions.install_packages(updates, "other")
   if len(remove) > 0:
    functions.remove_packages(remove)
   subprocess.run(f"cp {functions.cache_dir}/sha256 {functions.cache_dir}/current", shell=True)
   
