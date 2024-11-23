import os
import json
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Firebase initialization using environment variable for credentials
firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')

if not firebase_credentials:
    raise ValueError("FIREBASE_CREDENTIALS environment variable not set.")

# Parse the JSON string into a Python dictionary
cred_dict = json.loads(firebase_credentials)

# Initialize Firebase Admin SDK
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://chatapp-9711e-default-rtdb.firebaseio.com'  # Replace with your database URL
})

# References for database nodes
users_ref = db.reference('users')  # For storing user connections
messages_ref = db.reference('messages')  # For storing offline messages

# Reverse mapping of socket IDs to user IDs (in-memory cache for efficient lookups)
socket_to_user = {}

@socketio.on('connect')
def handle_connect():
    print(f"[INFO] Client connected: {request.sid}")

@socketio.on('register')
def handle_register(data):
    user_id = data.get('userId')
    if not user_id:
        emit('error', {'message': 'User ID is required for registration.'})
        return

    # Save user and prevent overwriting the socket-to-user mapping
    users_ref.child(user_id).set(request.sid)
    socket_to_user[request.sid] = user_id

    # Retrieve offline messages
    offline_messages = messages_ref.child(user_id).get() or []
    for message in offline_messages:
        emit('receiveMessage', message, to=request.sid)

    # Clear offline messages
    messages_ref.child(user_id).delete()

    print(f"[INFO] User {user_id} registered with socket ID {request.sid}")
    emit('registered', {'message': f'Registration successful for {user_id}'}, to=request.sid)


@socketio.on('sendMessage')
def handle_send_message(data):
    sender_id = data.get('senderId')
    recipient_id = data.get('recipientId')
    encrypted_message = data.get('encryptedMessage')

    if not all([sender_id, recipient_id, encrypted_message]):
        emit('error', {'message': 'Invalid data.'})
        return

    recipient_sid = users_ref.child(recipient_id).get()
    if recipient_sid:
        emit('receiveMessage', {
            'encryptedMessage': encrypted_message,
            'senderId': sender_id
        }, to=recipient_sid)
        emit('messageStatus', {'status': 'delivered'}, to=request.sid)
    else:
        messages_ref.child(recipient_id).push({
            'senderId': sender_id,
            'encryptedMessage': encrypted_message
        })
        emit('messageStatus', {'status': 'offline_saved'}, to=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    disconnected_sid = request.sid
    user_to_remove = socket_to_user.pop(disconnected_sid, None)

    if user_to_remove:
        users_ref.child(user_to_remove).delete()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
