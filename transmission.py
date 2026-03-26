#BLE uses 2.4 GHz frq

import asyncio
import json
import socket
import struct
import time
from bleak import BleakScanner


# [4-byte big-endian header_len][header_json][raw_payload_bytes]
# header_json contains metadata and list of blob lengths

#REMOTE_HOST=
#REMOTE_PORT=

#meant to send the information to a target later
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

#main function
async def main():
    queue = asyncio.Queue(maxsize=0)

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
        if(header.get("rssi") > -100 and header.get("rssi") != 127):#filter distance and 127 means missing or unknown signal so I'm filtering that out as well.
            if(76 not in device.metadata.get("manufacturer_data") and device.metadata.get("manufacturer_data") != {} and 6 not in device.metadata.get("manufacturer_data") and device.metadata.get("manufacturer_data") != {}):#filter apple and microsoft SIG
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

if __name__ == "__main__":
    asyncio.run(main())


