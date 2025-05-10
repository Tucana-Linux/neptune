#!/bin/python3
import logging
import os
import sys

from neptune.classes.Frontend import Frontend
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
   system = System()
   frontend = Frontend(system)
   system.settings.parse_config()
   system.settings.parse_repos()
   system.settings.parse_arguments()
   # operation always defined will exit if not
   run_operation(system.settings.operation, frontend)
