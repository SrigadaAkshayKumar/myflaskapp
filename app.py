from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

users = {}
offline_messages = {}

@app.route('/')
def index():
    return jsonify({"status": "Server is running", "message": "Welcome to Flask SocketIO server!"})

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    return jsonify({"status": "OK", "message": "Server is up and reachable!"})

@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")

@socketio.on('register')
def handle_register(data):
    user_id = data.get('userId')
    if not user_id:
        emit('error', {'message': 'User ID is required for registration.'})
        return
    users[user_id] = request.sid
    print(f"[INFO] User {user_id} registered with socket ID {request.sid}")
    emit('registered', {'message': f'Registration successful for {user_id}'}, to=request.sid)

    if user_id in offline_messages:
        for message in offline_messages[user_id]:
            emit('receiveMessage', message, to=request.sid)
        del offline_messages[user_id]

@socketio.on('sendMessage')
def handle_send_message(data):
    sender_id = data.get('senderId')
    recipient_id = data.get('recipientId')
    encrypted_message = data.get('encryptedMessage')

    if not all([sender_id, recipient_id, encrypted_message]):
        emit('error', {'message': 'Invalid data. Ensure senderId, recipientId, and encryptedMessage are provided.'})
        return

    print(f"[INFO] Sending message from {sender_id} to {recipient_id}: {encrypted_message}")

    if recipient_id in users:
        recipient_sid = users[recipient_id]
        emit(
            'receiveMessage',
            {'encryptedMessage': encrypted_message, 'senderId': sender_id},
            room=recipient_sid
        )
    else:
        if recipient_id not in offline_messages:
            offline_messages[recipient_id] = []
        offline_messages[recipient_id].append({
            'encryptedMessage': encrypted_message,
            'senderId': sender_id
        })
        print(f"[INFO] User {recipient_id} offline. Message saved.")

@socketio.on('disconnect')
def handle_disconnect():
    disconnected_sid = request.sid
    user_to_remove = next((user for user, sid in users.items() if sid == disconnected_sid), None)
    if user_to_remove:
        del users[user_to_remove]

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
