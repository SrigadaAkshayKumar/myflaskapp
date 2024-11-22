from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Enable CORS for all origins
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Store users and their socket IDs
users = {}  # {userId: socketId}
offline_messages = {}  # {recipientId: [{'senderId': senderId, 'encryptedMessage': message}]}

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

    # Register the user with their socket ID
    users[user_id] = request.sid
    print(f"[INFO] User {user_id} registered with socket ID {request.sid}")
    emit('registered', {'message': f'Registration successful for {user_id}'}, to=request.sid)

    # Deliver offline messages if any exist for this user
    if user_id in offline_messages:
        for message in offline_messages[user_id]:
            emit('receiveMessage', message, to=request.sid)
        del offline_messages[user_id]  # Clear the offline messages after delivery
        print(f"[INFO] Delivered offline messages to {user_id}")

@socketio.on('sendMessage')
def handle_send_message(data):
    sender_id = data.get('senderId')
    recipient_id = data.get('recipientId')
    encrypted_message = data.get('encryptedMessage')

    if not all([sender_id, recipient_id, encrypted_message]):
        emit('error', {'message': 'Invalid data. Ensure senderId, recipientId, and encryptedMessage are provided.'})
        return

    if recipient_id in users:
        recipient_sid = users[recipient_id]
        emit(
            'receiveMessage',
            {'encryptedMessage': encrypted_message, 'senderId': sender_id},
            room=recipient_sid
        )
        print(f"[INFO] Message sent from {sender_id} to {recipient_id}")
    else:
        # Store the message for later delivery
        if recipient_id not in offline_messages:
            offline_messages[recipient_id] = []
        offline_messages[recipient_id].append({'senderId': sender_id, 'encryptedMessage': encrypted_message})
        print(f"[INFO] Recipient {recipient_id} not connected. Message stored for offline delivery.")

@socketio.on('disconnect')
def handle_disconnect():
    disconnected_sid = request.sid
    user_to_remove = None
    for user_id, sid in users.items():
        if sid == disconnected_sid:
            user_to_remove = user_id
            break
    if user_to_remove:
        del users[user_to_remove]
        print(f"[INFO] User {user_to_remove} disconnected")
    else:
        print("[INFO] Unknown disconnection")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
