#!/usr/bin/env python

# interactice logging for search and rescue communications 
import argparse
import questionary
import json
from datetime import datetime, timezone

# status entry
#   status code - 0-9 (get values and use in prompt) - default 4
#   location - grid string, last assigned
#   location status - assigned, arrived, percentage, complete
#   transit - None, self, transport string
#   timestamp in zulu - generated on creation
class StatusEntry():
    "A single status entry for an SAR team"

    def __init__(self, team, location, location_status='assigned', transit=None, status_code=4):
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.team = team
        self.location = location
        self.location_status = location_status
        self.transit = transit
        self.status_code = status_code


# transmission entry
#   timestamp in zulu
#   dest string
#   src string
#   message string
class TransmissionEntry():
    "A single transmission entry"

    def __init__(self, msg, dest='high_bird', src='comms'):
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.msg = msg
        self.dest = dest
        self.src = src

# data structures
status_by_team = {} # list of status entries for each time
location_by_team = {} # last known location
transmissions = [] # list of transmissions in chronological order

def prompting_loop():
    "Loop until q[uit] is entered, adding entries based on typed inputs"

    done = False

    while not done:

        cmd = questionary.select("command:", choices=["status", "transmission", "quit"]).ask()

        if cmd == 'quit':
            break
        elif cmd == 'status':
            team = questionary.text('team:').ask()

            # initialize data structures if necessary
            status_by_team.setdefault(team, [])
            location_by_team.setdefault(team, 'unassigned')

            location = questionary.text('location: (grid or rtb)', default=location_by_team[team]).ask()
            location_status = questionary.select('location_status:', choices=['assigned', 'arrived', 'percentage', 'complete']).ask()
            transport = None
            if location_status == 'percentage':
                percentage_value = questionary.text(
                    "Enter percentage (0-100):",
                    validate=lambda text: text.isdigit() and 0 <= int(text) <= 100
                ).ask()
            elif location_status =='assigned' or location_status == 'complete':
                transit = questionary.text('transport:', default='self').ask()
            status_code = questionary.select('status_code:', choices=['None', '4 - ok', '6 - not ok']).ask()
            status_by_team[team].append(StatusEntry(team, location, location_status, transit, status_code))
            location_by_team[team] = location
        elif cmd == 'transmission':
            dest = questionary.text('Destination:', default='high bird').ask()
            src = questionary.text('Source:', default='comms').ask()
            message = questionary.text('Message:').ask()
            transmission = TransmissionEntry(dest, src, message)
            transmissions.append(transmission)
        else:
            raise Exception(f"Unknown command: {cmd}")
           

# handle command line arguments
def main():
    parser = argparse.ArgumentParser(
        description="Interactive logging for search and rescue communications."
    )

    # Optional flag: prompt
    parser.add_argument("-p", "--prompt", action="store_true", help="Prompt for status and transmissions")
    parser.add_argument("-j", "--json_file", default='./logs.json', help="json file location, defaults to ./logs.json")

    args = parser.parse_args()

    if args.prompt:
        prompting_loop()

    # save the result as json

    # fix for serialization
    status_by_team_dicts = {k: [status.__dict__ for status in v] for k, v in status_by_team.items()}

    transmissions_dicts = [transmission.__dict__ for transmission in transmissions]

    # combine to a single dict for json
    all_logs = {'status_by_team': status_by_team_dicts, 
                'location_by_team': location_by_team,
                'transmissions': transmissions_dicts}

    print(f'writing logs to json file {args.json_file}')
    with open(args.json_file, 'w') as f:
        json.dump(all_logs, f, indent=4)

    exit(0)

if __name__ == "__main__":
    main()
