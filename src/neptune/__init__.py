#!/bin/python3
import logging
import os
import sys

from neptune.classes.Frontend import Frontend
from neptune.classes.NeptuneSettings import NeptuneSettings
from neptune.classes.Repository import Repository
from neptune.classes.System import System

if os.geteuid() != 0:
   logging.error("This package manager must be run as root")
   sys.exit()


def run_operation(operation: str, frontend: Frontend):
   match operation:
      case "install":
         frontend.install()
      case "update":
         frontend.update()
      case "reinstall":
         frontend.reinstall()
      case "remove":
         frontend.remove()
      case "sync":
         frontend.sync()

def main():
   # also initalizes all the functions variables
   logging.debug(f"Arguments: {sys.argv}")
   settings = NeptuneSettings(arguments=sys.argv)
   system = System(settings)
   frontend = Frontend(system)
   system.settings.parse_config()
   system.settings.parse_repos()
   system.settings.parse_arguments()
   logging.basicConfig(stream=sys.stdout, level=system.settings.debug_level)
   # operation always defined will exit if not
   logging.debug(f"Operation: {system.settings.operation}")
   run_operation(system.settings.operation, frontend)
