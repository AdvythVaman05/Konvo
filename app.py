import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, async_mode='eventlet')

# MongoDB setup
client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017"))
db = client['chat_db']
messages_col = db['messages']
users_col = db['users']

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        session['username'] = username
        users_col.update_one({'username': username}, {'$setOnInsert': {'username': username}}, upsert=True)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('connect')
def handle_connect():
    messages = list(messages_col.find().sort('timestamp', 1))[-50:]
    for msg in messages:
        socketio.emit('chat message', {
            'username': msg['username'],
            'message': msg['message'],
            'timestamp': msg['timestamp'],
            'image': msg.get('image')
        })

@socketio.on('chat message')
def handle_chat_message(data):
    username = data['username']
    message = data['message']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg_data = {
        'username': username,
        'message': message,
        'timestamp': timestamp
    }
    messages_col.insert_one(msg_data)
    emit('chat message', msg_data, broadcast=True)

@socketio.on('image upload')
def handle_image(data):
    username = data['username']
    image = data['image']
    filename = secure_filename(data['filename'])
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, 'wb') as f:
        f.write(image.encode('latin1'))
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    image_url = url_for('uploaded_file', filename=filename)
    msg_data = {
        'username': username,
        'message': '[Image]',
        'timestamp': timestamp,
        'image': image_url
    }
    messages_col.insert_one(msg_data)
    emit('chat message', msg_data, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
