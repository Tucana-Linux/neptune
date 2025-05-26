import sys
from typing import Any
import yaml
arguments=sys.argv
if len(arguments) < 7:
    print("not enough arguments to package->yaml")
    sys.exit(1)
arguments.pop(0)
# 0 -- name
# 1 -- depends
# 2 -- version
# 3 -- download_size
# 4 -- install_size
# 5 -- epoch time
package : dict[str, dict[str, Any]]= {}
package[arguments[0]] = {}
if not arguments[1] == "":
    package[arguments[0]]["depends"] = arguments[1].split(" ")
package[arguments[0]]["version"] = arguments[2]
package[arguments[0]]["download_size"] = int(arguments[3])
package[arguments[0]]["install_size"] = int(arguments[4])
package[arguments[0]]["last_update"] = int(arguments[5])
print(yaml.dump(package).rstrip())
