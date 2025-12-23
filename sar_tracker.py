#!/usr/bin/env python

# interactice logging for search and rescue communications 
import argparse
import questionary
import storage
import spreadsheet
from datetime import datetime, timezone

# status entry
#   status code - 0-9 (get values and use in prompt) - default 4
#   location - grid string, last assigned
#   location status - assigned, arrived, percentage, complete
#   transit - None, self, transport string
#   timestamp in zulu - generated on creation
class StatusEntry():
    "A single status entry for a SAR team"

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

def prompting_loop(tactical_calls, writer, asker=None):
    """Loop until quit. is entered, adding entries based on typed inputs.

    `writer` should implement `add_status_entry(dict)` and `add_transmission(dict)` and
    have a `close()` method (returned by `storage.open_db_writer`).
    """

    done = False

    while not done:

        cmd = (asker.select if asker else questionary.select)("command:", choices=["status", "transmission", "export xlsx", "quit"]).ask()

        if cmd == 'quit':
            break
        elif cmd == 'status':
            team = (asker.text if asker else questionary.text)('team:').ask()

            # initialize data structures if necessary
            status_by_team.setdefault(team, [])
            location_by_team.setdefault(team, 'unassigned')

            location = (asker.text if asker else questionary.text)('location: (grid or rtb)', default=location_by_team[team]).ask()
            location_status = (asker.select if asker else questionary.select)('location_status:', choices=['assigned', 'arrived', 'percentage', 'complete']).ask()
            transit = None
            if location_status == 'percentage':
                percentage_value = (asker.text if asker else questionary.text)(
                    "Enter percentage (0-100):",
                    validate=lambda text: text.isdigit() and 0 <= int(text) <= 100
                ).ask()
                # store just the numeric percentage (e.g. '60%') so the DB and API
                # return the concise value and downstream consumers can display it
                location_status = f"{percentage_value}%"
            elif location_status =='assigned' or location_status == 'complete':
                transit = (asker.text if asker else questionary.text)('transport:', default='self').ask()
            status_code_choice = (asker.select if asker else questionary.select)('status_code:', choices=['None', '4 - ok', '6 - not ok']).ask()
            # normalize stored value to integer codes or None
            if status_code_choice == 'None':
                status_code = None
            else:
                # extract leading number if present (e.g. '4 - ok')
                try:
                    status_code = int(str(status_code_choice).split()[0])
                except Exception:
                    status_code = status_code_choice
            status_by_team[team].append(StatusEntry(team, location, location_status, transit, status_code))
            # persist incrementally (using persistent writer)
            writer.add_status_entry(status_by_team[team][-1].__dict__)
            location_by_team[team] = location
        elif cmd == 'transmission':
            # choose defaults from tactical_calls
            dest_default = tactical_calls[1] if len(tactical_calls) > 1 else tactical_calls[0]
            src_default = tactical_calls[0]
            dest = (asker.select if asker else questionary.select)('Destination:', choices=tactical_calls, default=dest_default).ask()
            src = (asker.select if asker else questionary.select)('Source:', choices=tactical_calls, default=src_default).ask()
            message = (asker.text if asker else questionary.text)('Message:').ask()
            transmission = TransmissionEntry(message, dest, src)
            transmissions.append(transmission)
            # persist incrementally (using persistent writer)
            writer.add_transmission(transmissions[-1].__dict__)
        elif cmd == 'export xlsx':
            # ask for filename and export current DB state
            default_fp = f"status-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.xlsx"
            xlsx_fp = (asker.text if asker else questionary.text)('XLSX filename:', default=default_fp).ask()
            try:
                ok = spreadsheet.export_to_xlsx(writer.db_path, xlsx_fp)
                print(f'exported xlsx: {xlsx_fp} -> {ok}')
            except Exception as e:
                print(f'failed to export xlsx: {e}')
        else:
            raise Exception(f"Unknown command: {cmd}")
           

# helper: load existing logs (if present) into runtime objects
def _convert_data_to_objects(data):
    """Convert a loaded JSON-like dict to runtime objects.

    Returns: (loaded_status, loaded_location, loaded_transmissions)
    """
    if not data:
        return {}, {}, []

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



# handle command line arguments
def main():
    parser = argparse.ArgumentParser(
        description="Interactive logging for search and rescue communications."
    )

    # Optional flag: prompt
    parser.add_argument("-p", "--prompt", action="store_true", help="Prompt for status and transmissions")
    parser.add_argument("-t", "--tactical-calls", nargs='+', metavar='TACTICAL_CALL', default=['comms', 'high bird'],
                        help="List of tactical calls for transmissions (default: ['comms','high bird'])")
    parser.add_argument("--sqlite-file", default='./logs.db', help="sqlite file location, defaults to ./logs.db")
    parser.add_argument("--import-json", metavar='JSON_FILE', help="Import a JSON file into sqlite and exit")
    parser.add_argument("--dump-json", metavar='JSON_FILE', help="Dump sqlite contents to JSON file and exit")
    parser.add_argument("--export-xlsx", metavar='XLSX_FILE', help="Export sqlite contents to XLSX file and exit")

    args = parser.parse_args()

    # handle import/dump operations first
    if args.import_json:
        ok = storage.import_json_to_db(args.import_json, args.sqlite_file)
        print(f"imported json to sqlite: {ok}")
        exit(0 if ok else 2)
    if args.dump_json:
        ok = storage.dump_db_to_json(args.sqlite_file, args.dump_json)
        print(f"dumped sqlite to json: {ok}")
        exit(0 if ok else 2)
    if args.export_xlsx:
        ok = spreadsheet.export_to_xlsx(args.sqlite_file, args.export_xlsx)
        print(f"exported sqlite to xlsx: {ok}")
        exit(0 if ok else 2)

    # load existing logs from sqlite (default)
    data = storage.load_db(args.sqlite_file)
    loaded_status, loaded_location, loaded_transmissions = _convert_data_to_objects(data)
    global status_by_team, location_by_team, transmissions
    status_by_team = loaded_status
    location_by_team = loaded_location
    transmissions = loaded_transmissions

    if args.prompt:
        writer = storage.open_db_writer(args.sqlite_file)
        try:
            prompting_loop(args.tactical_calls, writer)
        finally:
            writer.close()

    # continuous updates are persisted during the prompt loop; no final overwrite.
    exit(0)

if __name__ == "__main__":
    main()
