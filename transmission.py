#BLE uses 2.4 GHz frq
#most likely that signals send direct binary through peaks in the amplitude of these BLE signals
#need 2 transmitters and 2 recievers to each RPi can send signal to phone/car
#edit: signals are sent through packets, blobs are the raw binary of the signal, and other information about the signal is viewable


import asyncio
import json
import socket
import struct
import time
from bleak import BleakScanner

REMOTE_HOST = "192.0.2.10"   # replace
REMOTE_PORT = 9000           # replace

# [4-byte big-endian header_len][header_json][raw_payload_bytes]
# header_json contains metadata and list of blob lengths

async def sender(queue):
    reader, writer = await asyncio.open_connection(REMOTE_HOST, REMOTE_PORT)
    sock = writer.get_extra_info("socket")
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        while True:
            header_bytes, raw_bytes = await queue.get()
            header_len = struct.pack(">I", len(header_bytes))
            writer.write(header_len)
            writer.write(header_bytes)
            if raw_bytes:
                writer.write(raw_bytes)
            await writer.drain()
            queue.task_done()
    except asyncio.CancelledError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    queue = asyncio.Queue(maxsize=1000)

    def detection_callback(device, advertisement_data):
        ts = time.time()
        mfg = advertisement_data.manufacturer_data or {}
        svc = advertisement_data.service_data or {}
        blobs = []
        raw = bytearray()
        for k, v in mfg.items():
            b = bytes(v)
            blobs.append({"kind": "manufacturer", "key": int(k), "len": len(b)})
            raw.extend(b)
        for k, v in svc.items():
            b = bytes(v)
            blobs.append({"kind": "service", "key": str(k), "len": len(b)})
            raw.extend(b)

        header = {
            "timestamp": ts,
            "address": device.address,
            "rssi": device.rssi,
            "name": device.name or advertisement_data.local_name,
            "blobs": blobs
        }
        header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
        try:
            queue.put_nowait((header_bytes, bytes(raw)))
        except asyncio.QueueFull:
            pass
        if(header.get("rssi") > -100 and header.get("rssi") != 127):#filter distance
            if(76 not in device.metadata.get("manufacturer_data") and device.metadata.get("manufacturer_data") != {} and 6 not in device.metadata.get("manufacturer_data") and device.metadata.get("manufacturer_data") != {}):#filter apple SIG
                #print("Queue full, dropping packet", header.get("address"), raw, header.get("rssi"), device.metadata)
                print(f"here is the metadata where you can find the SIG identifier for the company who is sending the signal {list(device.metadata['manufacturer_data'].keys())[0]}")

    scanner = BleakScanner(detection_callback)
    await scanner.start()
    sender_task = asyncio.create_task(sender(queue))
    print("Scanning and forwarding (press Ctrl-C to stop)...")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await scanner.stop()
        sender_task.cancel()
        await sender_task


# def sender_files(package):
#     pass

# def packager(uuid, timestamp, address, rssi, name, blob, raw):#maybe just copy all package info from bleak?????? I'll see later
#     pass


if __name__ == "__main__":
    asyncio.run(main())


