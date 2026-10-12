import asyncio
import sqlite3
import time
from types import SimpleNamespace
from indoor_cycling.devices import Devices, HR


def test_saved_devices_survive_restart_and_forget(tmp_path):
    db = tmp_path / 'devices.sqlite3'
    receiver = Devices(db)
    receiver.initialize()
    receiver.discovered['fixture'] = {'identifier': 'fixture', 'name': 'Test watch'}
    receiver.save('fixture', 'My watch')
    restarted = Devices(db)
    assert restarted.saved() == [{'identifier': 'fixture', 'name': 'My watch'}]
    asyncio.run(restarted.forget('fixture'))
    assert receiver.saved() == []


def test_stale_and_disconnect_clear_real_heart_rate(tmp_path):
    receiver = Devices(tmp_path / 'db.sqlite3')
    receiver.state = 'connected'
    receiver._receive(None, bytes([0, 80]))
    assert receiver.snapshot()['heart_rate_bpm'] == 80
    receiver.updated = time.monotonic() - 6
    assert receiver.snapshot()['heart_rate_bpm'] is None
    receiver._lost(receiver.client)
    assert receiver.snapshot()['heart_rate_bpm'] is None
    assert receiver.snapshot()['state'] == 'disconnected'


def test_connect_subscribes_and_disconnects_without_control_writes(tmp_path, monkeypatch):
    events = []
    class Client:
        def __init__(self, identifier, **kwargs):
            self.is_connected = False
            self.services = SimpleNamespace(get_service=lambda uuid: object() if uuid == HR else None,
                get_characteristic=lambda uuid: SimpleNamespace(properties=['notify']))
        async def connect(self): self.is_connected = True
        async def start_notify(self, char, callback):
            events.append('notify')
            callback(char, bytes([0, 76]))
        async def disconnect(self):
            self.is_connected = False
            events.append('disconnect')
    monkeypatch.setattr('indoor_cycling.devices.BleakClient', Client)
    receiver = Devices(tmp_path / 'db.sqlite3')
    receiver.discovered['fixture'] = {}
    async def exercise():
        await receiver.connect('fixture')
        assert receiver.snapshot()['heart_rate_bpm'] == 76
        await receiver.disconnect()
        assert receiver.snapshot()['heart_rate_bpm'] is None
    asyncio.run(exercise())
    assert events == ['notify', 'disconnect']


def test_device_api_auth_and_unknown_selection():
    from fastapi.testclient import TestClient
    from indoor_cycling.server import app
    with TestClient(app) as client:
        for path in ('scan', 'connect', 'save', 'forget', 'disconnect'):
            assert client.post('/api/devices/' + path, json={'identifier': 'fixture', 'name': 'Watch'}).status_code == 401
        assert client.get('/api/devices').status_code == 401
        headers = {'X-Cycling-Token': 'test-only'}
        assert client.post('/api/devices/connect', headers=headers, json={'identifier': 'unknown'}).status_code == 400
        assert client.get('/devices').status_code == 200
        assert client.get('/api/devices', headers=headers).status_code == 200


def test_existing_samples_migration_and_live_source(tmp_path, monkeypatch):
    from indoor_cycling import server
    db = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE samples (session_id TEXT,timestamp TEXT,elapsed_s REAL,target_power_w INTEGER,actual_power_w INTEGER,heart_rate_bpm INTEGER,cadence_rpm INTEGER)')
        conn.execute("INSERT INTO samples VALUES ('old','time',1,90,90,125,82)")
    receiver = Devices(db)
    monkeypatch.setattr(server, 'DB', db)
    monkeypatch.setattr(server, 'devices', receiver)
    server.initialize()
    server.initialize()
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT heart_rate_source FROM samples').fetchone()[0] == 'SIMULATOR'
    receiver.identifier = 'fixture'
    receiver.state = 'connected'
    receiver._receive(None, bytes([0, 79]))
    assert server.live_snapshot()['heart_rate_bpm'] == 79
    assert server.live_snapshot()['heart_rate_source'] == 'BLE'
    receiver.updated = time.monotonic() - 6
    assert server.live_snapshot()['heart_rate_bpm'] is None
    assert server.live_snapshot()['heart_rate_source'] == 'BLE'


def test_mobile_history_auth_and_navigation():
    from fastapi.testclient import TestClient
    from indoor_cycling.server import app
    with TestClient(app) as client:
        for path in ('/', '/devices', '/history'):
            page = client.get(path)
            assert page.status_code == 200
            assert '主导航' in page.text
            assert 'viewport-fit=cover' in page.text
        assert client.get('/api/history').status_code == 401
        response = client.get('/api/history', headers={'X-Cycling-Token': 'test-only'})
        assert response.status_code == 200
        assert isinstance(response.json(), list)
