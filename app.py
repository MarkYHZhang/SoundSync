from flask import Flask
from flask import render_template, redirect, request
from flask_socketio import SocketIO
from flask_socketio import send, emit

from config import Config
from forms import CreateForm, JoinForm
import re
import utils
import time

# non-blocking sockets
from gevent import monkey
monkey.patch_all()

SYNCHRONIZATION_DELAY_CONST = 50/1000 # in sec
BATCH_PING_SIZE = 10

app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app)


class Device:
    session_id = ""
    timestamps = []
    ind = 0
    latency = 0

    def __init__(self, session_id):
        self.session_id = session_id

    def __eq__(self, other):
        return self.session_id == other.session_id


class Room:
    sync_code = ""
    vid_id = ""
    # sid -> device object
    devices = {}

    def __init__(self, sync_code, vid_id=""):
        self.sync_code = sync_code
        self.vid_id = vid_id

    def add_device(self, device):
        self.devices[device.session_id] = device

    def remove_device(self, sid):
        del self.devices[sid]

    def get_device(self, sid):
        return self.devices[sid]

# sync_code, room object
rooms = {}


@app.route('/', methods=['GET', 'POST'])
def landing():
    create_form = CreateForm()
    join_form = JoinForm()
    if create_form.validate_on_submit():
        regex = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<id>[A-Za-z0-9\-=_]{11})')
        match = regex.match(create_form.yt_url.data)
        if not match:
            return "Invalid URL"
        vid_id = match.group('id')
        sync_code = utils.randomString()
        rooms[sync_code] = Room(sync_code=sync_code, vid_id=vid_id)
        return redirect("/room?sc="+sync_code)

    if join_form.validate_on_submit():
        return redirect("/room?sc="+join_form.sync_code.data)

    return render_template('landing.html', create_form=create_form, join_form=join_form)


@app.route('/room', methods=['GET', 'POST'])
def room_handle():
    sync_code = request.args.get("sc")
    new_vid_form = CreateForm()
    room = rooms[sync_code]
    room.devices = {sid: dev for sid, dev in room.devices.items() if sid in online_devices}
    if new_vid_form.validate_on_submit():
        regex = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<id>[A-Za-z0-9\-=_]{11})')
        match = regex.match(new_vid_form.yt_url.data)
        if not match:
            return "Invalid URL"
        video_id = match.group('id')
        room.url = video_id
        return redirect("/room?sc="+sync_code)
    return render_template('room.html', new_vid_form=new_vid_form, sync_code=sync_code, num_devices=len(room.devices))


online_devices = []


@socketio.on('connect')
def connect():
    online_devices.append(request.sid)


@socketio.on('disconnect')
def disconnect():
    online_devices.remove(request.sid)


@socketio.on('get_vid_id')
def get_vid_id(json):
    sync_code = json['sync_code']
    emit('vid_id', {'vid_id': rooms[sync_code].vid_id})
    rooms[sync_code].add_device(Device(request.sid))


@socketio.on('init_cmd')
def init_cmd(json):
    sync_code = json['sync_code']
    cmd = json['cmd']
    room = rooms[sync_code]
    room.devices = {sid: dev for sid, dev in room.devices.items() if sid in online_devices}
    for sid, device in room.devices.items():
        device.timestamps = []
        device.ind = 0
        for i in range(BATCH_PING_SIZE):
            device.timestamps.append(time.time())
            emit("ping_to", {}, room=sid)
    while not all([dev.ind == BATCH_PING_SIZE for dev in room.devices.values()]):
        time.sleep(0.001)  # SLEEPS FOR 0.1s
    max_latency = max([dev.latency for dev in room.devices.values()])
    org_ts = time.time()
    for sid, device in room.devices.items():
        loop_latency = time.time() - org_ts
        delay = max_latency + SYNCHRONIZATION_DELAY_CONST - device.latency - loop_latency
        # print(delay, max_latency, SYNCHRONIZATION_DELAY_CONST, device.latency, loop_latency)
        emit("delayed_cmd", {'cmd': cmd, 'delay': delay}, room=sid)


@socketio.on('pong_back')
def pong_back(json):
    sync_code = json['sync_code']
    device_id = request.sid
    device = rooms[sync_code].get_device(device_id)
    cur_latency = (time.time() - device.timestamps[device.ind]) / 2
    device.latency = (device.latency * device.ind + cur_latency) / (device.ind + 1)
    device.ind += 1


if __name__ == '__main__':
    socketio.run(app)
