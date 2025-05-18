from GeneralSystem import GeneralSystem
import sys
import json
from enum import Enum

from specific_system.GarbageSystem import GarbageSystem
from specific_system.SafetySystem import SafetySystem
from specific_system.CountSystem import CountSystem
from specific_system.guardSystem import GuardSystem

class SystemType(Enum):
    GARBAGE = 0
    SAFETY = 1
    GUARD = 2
    PEOPLE_COUNT = 3

def read_system_type(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
        type = config.get("type", "None")
        
        try:
            return SystemType[type]
        except KeyError:
            print(f"""Please specify system type in the config file.
                Available types: {', '.join([e.name for e in SystemType])}
                """
                )
            sys.exit(1)

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python app_garbage_detection.py <config_path>...")
        sys.exit(1)

    paths = sys.argv[1:]
    print(f"Received paths: {paths}")

    config_path = paths[0]
    # detector = GeneralSystem(config_path)

    type = read_system_type(config_path)

    detector = None
    if type == SystemType.GARBAGE:    
        detector = GarbageSystem(config_path)
    elif type == SystemType.SAFETY:
        detector = SafetySystem(config_path)
    elif type == SystemType.GUARD:
        detector = GuardSystem(config_path)
    elif type == SystemType.PEOPLE_COUNT:
        detector = CountSystem(config_path)

    if detector is None:
        print(f"System type {type} not supported")
        sys.exit(1)
    
    detector.start_operation()

