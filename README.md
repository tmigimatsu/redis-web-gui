# redis-web-gui
Browser interface for monitoring Redis keys

### Basic Usage

Run `./server.py` and go to `http://localhost:8000` in the browser.

#### Reading Redis keys
- Keys will appear and update every 0.5 seconds.
- Numerical arrays stored as space-separated strings in Redis (e.g. "0.0 1.0 1.0") will appear as input arrays in the browser.

#### Writing Redis keys
- To change a key's value, simply input a value and click the `SET` button or hit `<enter>`.
- To toggle a key between 0 and its current value, click the `TOG` button or hit `<alt-enter>`.
- To set an entire array by repeating the value of the first element, click the `REP` button or hit `<shift-enter>`.

### Advanced Usage
```
server.py [-h] [-hp HTTP_PORT] [-wp WS_PORT] [-rh REDIS_HOST]
          [-rp REDIS_PORT] [-rd REDIS_DB] [-r REFRESH_RATE]
          [--realtime]

optional arguments:
  -h, --help            show this help message and exit
  -hp HTTP_PORT, --http_port HTTP_PORT
                        HTTP Port (default: 8000)
  -wp WS_PORT, --ws_port WS_PORT
                        WebSocket port (default: 8001)
  -rh REDIS_HOST, --redis_host REDIS_HOST
                        Redis hostname (default: localhost)
  -rp REDIS_PORT, --redis_port REDIS_PORT
                        Redis port (default: 6379)
  -rd REDIS_DB, --redis_db REDIS_DB
                        Redis database number (default: 0)
  -r REFRESH_RATE, --refresh_rate REFRESH_RATE
                        Redis refresh rate in seconds (default: 0.5)
  --realtime            Subscribe to realtime Redis SET pubsub notifications
```
