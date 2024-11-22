from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import firebase_admin
from firebase_admin import credentials, db

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Firebase initialization
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")  # Load Firebase credentials from environment variables

if not firebase_credentials:
    raise ValueError("FIREBASE_CREDENTIALS environment variable not set.")
  
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://chatapp-9711e-default-rtdb.firebaseio.com'  # Replace with your Firebase Realtime Database URL
})

# References for Firebase database nodes
users_ref = db.reference('users')  # For storing user connections
messages_ref = db.reference('messages')  # For storing offline messages

# SocketIO Handlers
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

    # Save user connection with their socket ID in the Firebase database
    users_ref.child(user_id).set(request.sid)
    print(f"[INFO] User {user_id} registered with socket ID {request.sid}")
    
    emit('registered', {'message': f'Registration successful for {user_id}'}, to=request.sid)

    # Deliver any offline messages for the user
    offline_messages = messages_ref.child(user_id).get() or []
    for message in offline_messages:
        emit('receiveMessage', message, to=request.sid)
    
    # Clear offline messages after delivery
    messages_ref.child(user_id).delete()
    print(f"[INFO] Delivered offline messages to {user_id}")

@socketio.on('sendMessage')
def handle_send_message(data):
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

    # Find user with this socket ID and remove their connection from Firebase
    all_users = users_ref.get() or {}
    for user_id, sid in all_users.items():
        if sid == disconnected_sid:
            user_to_remove = user_id
            break
    
    if user_to_remove:
        users_ref.child(user_to_remove).delete()
        print(f"[INFO] User {user_to_remove} disconnected")

if __name__ == '__main__':
    # Define port from environment variable, default to 8080
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
