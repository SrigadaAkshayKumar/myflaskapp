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

# SocketIO handlers
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
    
    # Save user with their socket ID in the database
    users_ref.child(user_id).set(request.sid)
    print(f"[INFO] User {user_id} registered with socket ID {request.sid}")
    emit('registered', {'message': f'Registration successful for {user_id}'}, to=request.sid)

    # Deliver offline messages if any exist for this user
    offline_messages = messages_ref.child(user_id).get() or []
    for message in offline_messages:
        emit('receiveMessage', message, to=request.sid)
    # Clear offline messages after delivery
    messages_ref.child(user_id).delete()
    print(f"[INFO] Delivered offline messages to {user_id}")

@socketio.on('sendMessage')
def handle_send_message(data):
    print(f"Received message data: {data}")  # Log the incoming message data
    sender_id = data.get('senderId')
    recipient_id = data.get('recipientId')
    encrypted_message = data.get('encryptedMessage')

    if not all([sender_id, recipient_id, encrypted_message]):
        emit('error', {'message': 'Invalid data. Ensure senderId, recipientId, and encryptedMessage are provided.'})
        return

    print(f"[INFO] Sending message from {sender_id} to {recipient_id}: {encrypted_message}")

    # Check if recipient is online
    recipient_sid = users_ref.child(recipient_id).get()
    if recipient_sid:
        emit('receiveMessage', {
            'encryptedMessage': encrypted_message,
            'senderId': sender_id
        }, room=recipient_sid)
        print(f"[INFO] Message sent to {recipient_id}")
    else:
        # Save the message for offline delivery
        messages_ref.child(recipient_id).push({
            'senderId': sender_id,
            'encryptedMessage': encrypted_message
        })
        print(f"[INFO] User {recipient_id} is offline. Message saved.")


@socketio.on('disconnect')
def handle_disconnect():
    disconnected_sid = request.sid
    user_to_remove = None

    # Find user with this socket ID and remove them
    all_users = users_ref.get() or {}
    for user_id, sid in all_users.items():
        if sid == disconnected_sid:
            user_to_remove = user_id
            break
    
    if user_to_remove:
        users_ref.child(user_to_remove).delete()
        print(f"[INFO] User {user_to_remove} disconnected")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
