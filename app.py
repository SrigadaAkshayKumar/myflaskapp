from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Enable CORS for all origins
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Store users and their socket IDs
users = {}

@app.route('/')
def index():
    return jsonify({"status": "Server is running", "message": "Welcome to Flask SocketIO server!"})

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    return jsonify({"status": "OK", "message": "Server is up and reachable!"})

@socketio.on('register')
def handle_register(data):
    user_id = data.get('userId')
    if not user_id:
        emit('error', {'message': 'User ID is required for registration.'})
        return

    users[user_id] = request.sid  # Map user ID to socket ID
    print(f"[INFO] User {user_id} registered with socket ID {request.sid}")
    emit('registered', {'message': f'Registration successful for {user_id}'})

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
        print(f"[WARNING] Recipient {recipient_id} not connected")
        emit('error', {'message': f'Recipient {recipient_id} not connected'})

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
    import os
    port = int(os.environ.get('PORT', 5000))  # Default to 5000 if PORT is not set
    socketio.run(app, host='0.0.0.0', port=port)

