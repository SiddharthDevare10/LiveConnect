import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import jsonify, request, render_template, session, url_for

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
    email = db.Column(db.String(120), unique=True, nullable=False)  # Added email field
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
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check if passwords match
        if password != confirm_password:
            error = 'Passwords do not match'
        else:
            # Check if username or email already exists
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            if existing_user:
                error = 'Username or email already exists'
            else:
                user = User(username=username, email=email, password=password)
                db.session.add(user)
                db.session.commit()
                return redirect(url_for('login'))
    return render_template('register.html', error=error)

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
        return render_template('login.html', error="Invalid username or password")

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
        video_url = room_data.current_video_url or ""
        return render_template('room.html', room_id=room_id, current_video_url=video_url)
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

socketio.on('join')
def handle_join(data):
    room = data['room']
    username = session.get('username', 'Unknown')
    join_room(room)
    emit('message', f"{username} has entered the room.", room=room)

@socketio.on('message')
def handle_message(msg):
    username = session.get('username', 'Unknown')
    room = None
    # If you send room info with the message, use it here
    # room = msg.get('room')
    # emit('message', f"{username}: {msg['text']}", room=room)
    # For now, broadcast to all
    send(f"{username}: {msg}", broadcast=True)

@socketio.on('video_played')
def handle_video_played(data):
    room = data['room']
    emit('video_played', room=room)

@socketio.on('video_uploaded')
def handle_video_uploaded(video_url):
    # You may want to send this to a specific room
    emit('new_video', video_url, broadcast=True)

# --- AUDIO CHAT SIGNALING EVENTS ---

@socketio.on('join_audio')
def handle_join_audio(data):
    room = data['room']
    username = data['username']
    user_id = request.sid
    join_room(room)
    emit('user_joined_audio', {'userId': user_id, 'username': username}, room=room, include_self=False)

@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    offer = data['offer']
    to = data['to']
    emit('webrtc_offer', {'offer': offer, 'from': request.sid}, room=to)

@socketio.on('webrtc_answer')
def handle_webrtc_answer(data):
    answer = data['answer']
    to = data['to']
    emit('webrtc_answer', {'answer': answer, 'from': request.sid}, room=to)

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    candidate = data['candidate']
    to = data['to']
    emit('ice_candidate', {'candidate': candidate, 'from': request.sid}, room=to)

@socketio.on('disconnect')
def handle_disconnect():
    # Optionally, notify others in the room
    pass

@socketio.on('leave_audio')
def handle_leave_audio(data):
    room = data['room']
    username = data['username']
    user_id = request.sid
    leave_room(room)
    emit('user_left_audio', {'userId': user_id, 'username': username}, room=room)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)