import os
os.environ['CYCLING_TOKEN'] = 'test-only'
from fastapi.testclient import TestClient
from indoor_cycling.server import app, trainer

def test_authorization():
    with TestClient(app) as client:
        assert client.get('/api/status').status_code == 401

def test_simulator_flow():
    with TestClient(app) as client:
        headers = {'X-Cycling-Token': 'test-only'}
        assert client.post('/api/power',headers=headers,json={'watts':151}).status_code == 422
        assert client.post('/api/power',headers=headers,json={'watts':100}).json()['target_power_w']==100
        assert client.post('/api/start',headers=headers).json()['state']=='running'
        assert client.get('/api/status',headers=headers).json()['mode']=='SIMULATOR'
        assert client.post('/api/pause',headers=headers).json()['state']=='paused'
        assert client.post('/api/stop',headers=headers).json()['state']=='ended'
