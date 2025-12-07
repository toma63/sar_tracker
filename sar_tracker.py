#!/usr/bin/env python

# interactice logging for search and rescue communications 
import argparse
import questionary
import json
from datetime import datetime, timezone
from pathlib import Path

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

    def __init__(self, msg, dest='high bird', src='comms'):
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.msg = msg
        self.dest = dest
        self.src = src

# data structures
status_by_team = {} # list of status entries for each time
location_by_team = {} # last known location
transmissions = [] # list of transmissions in chronological order

def prompting_loop(tactical_calls):
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
            transit = None
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
            # choose defaults from tactical_calls
            dest_default = tactical_calls[1] if len(tactical_calls) > 1 else tactical_calls[0]
            src_default = tactical_calls[0]
            dest = questionary.select('Destination:', choices=tactical_calls, default=dest_default).ask()
            src = questionary.select('Source:', choices=tactical_calls, default=src_default).ask()
            message = questionary.text('Message:').ask()
            transmission = TransmissionEntry(message, dest, src)
            transmissions.append(transmission)
        else:
            raise Exception(f"Unknown command: {cmd}")
           

# helper: load existing logs (if present) into runtime objects
def load_logs(fp):
    p = Path(fp)
    if not p.exists():
        return {}, {}, []
    with p.open('r') as f:
        data = json.load(f)

    loaded_status = {}
    for team, entries in data.get('status_by_team', {}).items():
        loaded_status.setdefault(team, [])
        for e in entries:
            s = StatusEntry(e.get('team', team), e.get('location'), e.get('location_status', 'assigned'), e.get('transit'), e.get('status_code', 4))
            if 'timestamp' in e:
                s.timestamp = e['timestamp']
            loaded_status[team].append(s)

    loaded_location = data.get('location_by_team', {}) or {}

    loaded_transmissions = []
    for t in data.get('transmissions', []):
        tr = TransmissionEntry(t.get('msg'), t.get('dest', 'high bird'), t.get('src', 'comms'))
        if 'timestamp' in t:
            tr.timestamp = t['timestamp']
        loaded_transmissions.append(tr)

    return loaded_status, loaded_location, loaded_transmissions


def save_logs(fp):
    status_by_team_dicts = {k: [status.__dict__ for status in v] for k, v in status_by_team.items()}
    transmissions_dicts = [transmission.__dict__ for transmission in transmissions]
    all_logs = {'status_by_team': status_by_team_dicts,
                'location_by_team': location_by_team,
                'transmissions': transmissions_dicts}
    p = Path(fp)
    with p.open('w') as f:
        json.dump(all_logs, f, indent=4)


# handle command line arguments
def main():
    parser = argparse.ArgumentParser(
        description="Interactive logging for search and rescue communications."
    )

    # Optional flag: prompt
    parser.add_argument("-p", "--prompt", action="store_true", help="Prompt for status and transmissions")
    parser.add_argument("-j", "--json_file", default='./logs.json', help="json file location, defaults to ./logs.json")
    parser.add_argument("-t", "--tactical-calls", nargs='+', metavar='TACTICAL_CALL', default=['comms', 'high bird'],
                        help="List of tactical calls for transmissions (default: ['comms','high bird'])")

    args = parser.parse_args()

    # load existing logs (if any)
    loaded_status, loaded_location, loaded_transmissions = load_logs(args.json_file)
    global status_by_team, location_by_team, transmissions
    status_by_team = loaded_status
    location_by_team = loaded_location
    transmissions = loaded_transmissions

    if args.prompt:
        prompting_loop(args.tactical_calls)

    # save the result as json
    print(f'writing logs to json file {args.json_file}')
    save_logs(args.json_file)

    exit(0)

if __name__ == "__main__":
    main()
