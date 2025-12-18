import json
import os
import tempfile

import storage


def make_db_path():
    fd, path = tempfile.mkstemp(prefix="test_sar_", suffix=".db")
    os.close(fd)
    # ensure removed so storage.init_db can create clean DB
    try:
        os.remove(path)
    except OSError:
        pass
    return path


def test_add_status_and_transmission_roundtrip():
    db = make_db_path()
    try:
        status1 = {
            "team": "Alpha",
            "location": "Grid1",
            "location_status": "assigned",
            "transit": "self",
            "status_code": 4,
            "timestamp": "20251218T120000Z",
        }

        status2 = {
            "team": "Alpha",
            "location": "Grid2",
            "location_status": "arrived",
            "transit": None,
            "status_code": 4,
            "timestamp": "20251218T120500Z",
        }

        status_other = {
            "team": "Bravo",
            "location": "GridB",
            "location_status": "assigned",
            "transit": "vehicle",
            "status_code": 4,
            "timestamp": "20251218T121000Z",
        }

        tx = {
            "timestamp": "20251218T121100Z",
            "dest": "high bird",
            "src": "comms",
            "msg": "Test message",
        }

        storage.add_status_entry(db, status1)
        storage.add_status_entry(db, status2)
        storage.add_status_entry(db, status_other)
        storage.add_transmission(db, tx)

        data = storage.load_db(db)
        assert data is not None

        # verify teams
        assert "Alpha" in data["status_by_team"]
        assert "Bravo" in data["status_by_team"]

        # Alpha should have two entries, Bravo one
        assert len(data["status_by_team"]["Alpha"]) == 2
        assert len(data["status_by_team"]["Bravo"]) == 1

        # location_by_team should reflect last known
        assert data["location_by_team"]["Alpha"] == "Grid2"
        assert data["location_by_team"]["Bravo"] == "GridB"

        # transmissions should include our message
        assert any(t.get("msg") == "Test message" for t in data.get("transmissions", []))

    finally:
        try:
            os.remove(db)
        except OSError:
            pass


def test_save_dump_and_import_json_roundtrip():
    db = make_db_path()
    try:
        # prepare an all_logs dict similar to CLI usage
        all_logs = {
            "status_by_team": {
                "Alpha": [
                    {"team": "Alpha", "location": "G1", "location_status": "assigned", "transit": "self", "status_code": 4, "timestamp": "20251218T120000Z"}
                ]
            },
            "location_by_team": {"Alpha": "G1"},
            "transmissions": [
                {"timestamp": "20251218T120100Z", "dest": "high bird", "src": "comms", "msg": "hello"}
            ]
        }

        # save_db should create the DB contents
        storage.save_db(db, all_logs)
        data = storage.load_db(db)
        assert data is not None
        assert "Alpha" in data["status_by_team"]
        assert any(t.get("msg") == "hello" for t in data.get("transmissions", []))

        # dump to json file
        tmpjson = db + ".json"
        try:
            ok = storage.dump_db_to_json(db, tmpjson)
            assert ok is True
            assert os.path.exists(tmpjson)

            # import into a new DB
            db2 = make_db_path()
            try:
                ok2 = storage.import_json_to_db(tmpjson, db2)
                assert ok2 is True
                data2 = storage.load_db(db2)
                assert data2 is not None
                assert data2.get("location_by_team", {}).get("Alpha") == "G1"
            finally:
                try:
                    os.remove(db2)
                except OSError:
                    pass
        finally:
            try:
                os.remove(tmpjson)
            except OSError:
                pass

    finally:
        try:
            os.remove(db)
        except OSError:
            pass
