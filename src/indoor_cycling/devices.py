"""Local BLE heart-rate receiver. Never writes trainer control characteristics."""
import asyncio
import sqlite3
import time
from bleak import BleakClient, BleakScanner
from .protocol import heart_rate_measurement

HR = '0000180d-0000-1000-8000-00805f9b34fb'
MEASUREMENT = '00002a37-0000-1000-8000-00805f9b34fb'

class Devices:
    def __init__(self, database):
        self.database = database
        self.lock = asyncio.Lock()
        self.client = None
        self.identifier = None
        self.bpm = None
        self.updated = None
        self.state = 'disconnected'
        self.error = None
        self.discovered = {}

    def initialize(self):
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS devices (identifier TEXT PRIMARY KEY, name TEXT NOT NULL)')

    def saved(self):
        with sqlite3.connect(self.database) as db:
            return [dict(identifier=i, name=n) for i, n in db.execute('SELECT identifier,name FROM devices ORDER BY name')]

    async def scan(self):
        async with self.lock:
            found = await BleakScanner.discover(timeout=10, return_adv=True)
            self.discovered = {
                address: {'identifier': address, 'name': adv.local_name or device.name or '未命名心率设备', 'rssi': adv.rssi}
                for address, (device, adv) in found.items()
                if HR in adv.service_uuids or 'coros' in (adv.local_name or device.name or '').lower()
            }
            return list(self.discovered.values())

    def save(self, identifier, name):
        if identifier not in self.discovered and identifier not in {d['identifier'] for d in self.saved()}:
            raise ValueError('请先扫描设备')
        with sqlite3.connect(self.database) as db:
            db.execute('INSERT INTO devices VALUES (?,?) ON CONFLICT(identifier) DO UPDATE SET name=excluded.name', (identifier, name))

    async def forget(self, identifier):
        async with self.lock:
            if identifier == self.identifier:
                await self._disconnect()
            with sqlite3.connect(self.database) as db:
                db.execute('DELETE FROM devices WHERE identifier=?', (identifier,))

    def snapshot(self):
        age = None if self.updated is None else round(time.monotonic() - self.updated, 1)
        fresh = self.state == 'connected' and age is not None and age <= 5
        return {'state': self.state, 'identifier': self.identifier, 'heart_rate_bpm': self.bpm if fresh else None,
                'age_s': age, 'stale': not fresh, 'error': self.error}

    def _lost(self, client):
        if client is self.client:
            self.state = 'disconnected'
            self.bpm = None
            self.updated = None

    def _receive(self, characteristic, data):
        try:
            bpm = heart_rate_measurement(bytes(data))
        except (ValueError, IndexError):
            self.error = '收到无效心率数据'
            return
        self.bpm = bpm
        self.updated = time.monotonic()
        self.error = None

    async def _disconnect(self):
        client, self.client = self.client, None
        self.state = 'disconnected'
        self.identifier = None
        self.bpm = self.updated = None
        if client:
            await client.disconnect()

    async def disconnect(self):
        async with self.lock:
            await self._disconnect()

    async def connect(self, identifier):
        async with self.lock:
            if identifier not in self.discovered and identifier not in {d['identifier'] for d in self.saved()}:
                raise ValueError('请先扫描或保存设备')
            await self._disconnect()
            self.state = 'connecting'
            self.error = None
            client = BleakClient(identifier, timeout=20, disconnected_callback=self._lost)
            self.client = client
            self.identifier = identifier
            try:
                await client.connect()
                service = client.services.get_service(HR)
                char = client.services.get_characteristic(MEASUREMENT)
                if not service or not char or 'notify' not in char.properties:
                    raise ValueError('设备未提供标准心率通知')
                await client.start_notify(char, self._receive)
                if not client.is_connected:
                    raise ValueError('设备已断开，请重新连接')
                self.state = 'connected'
            except Exception:
                await self._disconnect()
                self.error = '连接失败，请检查心率广播与蓝牙占用'
                raise
