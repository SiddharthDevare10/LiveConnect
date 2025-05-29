import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO, send, emit, join_room

UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'ogg'}

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)

# Ensure uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(50), unique=True, nullable=False)
    pin = db.Column(db.String(10), nullable=False)
    host_username = db.Column(db.String(50), nullable=False)
    current_video_url = db.Column(db.String(200), nullable=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return {'error': 'Username already exists'}, 400
        
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/main', methods=['POST'])
def main():
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        session['username'] = username
        rooms = Room.query.all()
        return render_template('main.html', rooms=rooms)
    else:
        return redirect(url_for('login'))

@app.route('/create_room', methods=['POST'])
def create_room():
    room_id = request.form['room_id']
    pin = request.form['pin']
    host_username = session['username']

    existing_room = Room.query.filter_by(room_id=room_id).first()
    if existing_room:
        return {'error': 'Room ID already exists. Please choose a different one.'}, 400

    room = Room(room_id=room_id, pin=pin, host_username=host_username)
    db.session.add(room)
    db.session.commit()
    return redirect(url_for('room', room_id=room_id))

@app.route('/join_room', methods=['POST'])
def join_room_route():
    data = request.get_json()
    room_id = data.get('room_id')
    pin = data.get('pin')

    room = Room.query.filter_by(room_id=room_id, pin=pin).first()
    if room:
        return {'message': 'Room joined successfully.', 'room_id': room_id}, 200
    else:
        return {'error': 'Invalid room ID or pin.'}, 400

@app.route('/room/<room_id>')
def room(room_id):
    room_data = Room.query.filter_by(room_id=room_id).first()
    if room_data:
        return render_template('room.html', room_id=room_id, current_video_url=room_data.current_video_url)
    return "Room not found", 404

@app.route('/upload/<room_id>', methods=['POST'])
def upload(room_id):
    if 'file' not in request.files:
        return {'error': 'No file part'}, 400
    file = request.files['file']
    if file.filename == '':
        return {'error': 'No selected file'}, 400
    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)

        room = Room.query.filter_by(room_id=room_id).first()
        room.current_video_url = url_for('uploaded_file', filename=filename, _external=True)
        db.session.commit()

        socketio.emit('new_video', room.current_video_url, room=room_id)
        return {'video_url': room.current_video_url}
    else:
        return {'error': 'File type not allowed'}, 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/close_room/<room_id>', methods=['DELETE'])
def close_room(room_id):
    room = Room.query.filter_by(room_id=room_id).first()
    if room:
        db.session.delete(room)
        db.session.commit()
        socketio.emit('message', f"The room {room_id} has been closed.")
        return {'message': 'Room closed successfully.'}, 200
    else:
        return {'error': 'Room not found.'}, 404

@socketio.on('play_video')
def handle_play_video(room_id):
    emit('play_video', room=room_id)

@socketio.on('pause_video')
def handle_pause_video(room_id):
    emit('pause_video', room=room_id)

@socketio.on('message')
def handleMessage(msg):
    username = session['username']
    send(username + ': ' + msg, broadcast=True)

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    emit('message', f"{session['username']} has entered the room.", room=room)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, port=5001, debug=True)
