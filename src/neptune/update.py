import subprocess
import sys
import os
import requests
from packaging.version import Version

from neptune import functions
'''
Update Block
'''
def check_for_updates():
   updates = []

   for package in functions.installed_packages:
      # ignore unavailable packages
      if not functions.check_if_packages_exist(package):
         continue
      best_repo = functions.find_repo_with_best_version(package)
      if Version(best_repo.get_package_ver(package)) > Version(functions.versions[package]):
         updates.append(package)
      

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
   
