import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import base64
import os
from PIL import Image
import io
import uuid

# Initialize Supabase client
SUPABASE_URL = "https://iieqdcmcbtpswbtadpqm.supabase.co"  # Replace with your Supabase Project URL
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlpZXFkY21jYnRwc3didGFkcHFtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDUwMDA3MDQsImV4cCI6MjA2MDU3NjcwNH0.o0R-s0fSn_ljIqfwdXTTpW51kPqTr5ASbopk5HnDzFM"  # Replace with your Supabase Anon Public Key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Streamlit page config
st.set_page_config(page_title="Real-Time Chat App", layout="wide")

# Session state initialization
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'recipient_id' not in st.session_state:
    st.session_state['recipient_id'] = None
if 'messages' not in st.session_state:
    st.session_state['messages'] = []

# Authentication Functions
def login():
    st.subheader("Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", key="login_password", type="password")
    if st.button("Login"):
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state['user'] = response.user
            st.success("Logged in successfully!")
        except Exception as e:
            st.error(f"Login failed: {str(e)}")

def signup():
    st.subheader("Sign Up")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Password", key="signup_password", type="password")
    if st.button("Sign Up"):
        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            st.session_state['user'] = response.user
            st.success("Account created! Please log in.")
        except Exception as e:
            st.error(f"Sign up failed: {str(e)}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.session_state['recipient_id'] = None
    st.session_state['messages'] = []
    st.success("Logged out successfully!")

# Image Upload Function
def upload_image(file):
    if file is not None:
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{st.session_state['user'].id}_{timestamp}_{file.name}"
        # Upload to Supabase Storage
        try:
            file_bytes = file.read()
            supabase.storage.from_("chat-images").upload(filename, file_bytes, {
                "content-type": file.type
            })
            # Get public URL
            url = supabase.storage.from_("chat-images").get_public_url(filename)
            return url
        except Exception as e:
            st.error(f"Image upload failed: {str(e)}")
    return None

# Display Image
def display_image(url):
    if url:
        st.image(url, width=200)

# Fetch Users
def get_users():
    try:
        users = supabase.table("users").select("id, email").execute()
        return [(user['id'], user['email']) for user in users.data if user['id'] != st.session_state['user'].id]
    except:
        return []

# Load Message History
def load_messages(recipient_id):
    if recipient_id:
        try:
            messages = supabase.table("messages").select("*").or_(f"sender_id.eq.{st.session_state['user'].id},recipient_id.eq.{st.session_state['user'].id}").or_(f"sender_id.eq.{recipient_id},recipient_id.eq.{recipient_id}").order("created_at").execute()
            st.session_state['messages'] = messages.data
        except Exception as e:
            st.error(f"Failed to load messages: {str(e)}")

# Real-time Message Subscription
def subscribe_to_messages():
    def on_message(payload):
        if payload['eventType'] == 'INSERT':
            new_message = payload['record']
            if (new_message['sender_id'] == st.session_state['user'].id or new_message['recipient_id'] == st.session_state['user'].id) and \
               (new_message['sender_id'] == st.session_state['recipient_id'] or new_message['recipient_id'] == st.session_state['recipient_id']):
                st.session_state['messages'].append(new_message)
                st.rerun()

    try:
        supabase.table("messages").on("INSERT", on_message).subscribe()
    except Exception as e:
        st.error(f"Subscription failed: {str(e)}")

# Chat Interface
def chat_interface():
    st.subheader("Chat")
    
    # Logout button
    if st.button("Logout"):
        logout()
        st.rerun()

    # Select recipient
    users = get_users()
    if not users:
        st.warning("No other users available to chat with.")
        return

    recipient_email = st.selectbox("Select user to chat with", [user[1] for user in users])
    if recipient_email:
        st.session_state['recipient_id'] = next(user[0] for user in users if user[1] == recipient_email)
        load_messages(st.session_state['recipient_id'])
    
    # Subscribe to real-time updates
    if st.session_state['recipient_id']:
        subscribe_to_messages()
    
    # Display messages
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state['messages']:
            sender_email = next((user[1] for user in users if user[0] == msg['sender_id']), msg['sender_id'])
            if msg['sender_id'] == st.session_state['user'].id:
                st.markdown(f"**You** ({msg['created_at']}): {msg['content']}")
                if msg['image_url']:
                    display_image(msg['image_url'])
            else:
                st.markdown(f"**{sender_email}** ({msg['created_at']}): {msg['content']}")
                if msg['image_url']:
                    display_image(msg['image_url'])
    
    # Message input
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        message = st.text_input("Type a message", key="message_input")
    with col2:
        uploaded_file = st.file_uploader("Upload Image", type=["jpg", "png"], key="image_upload")
    with col3:
        if st.button("Send"):
            if message or uploaded_file:
                image_url = upload_image(uploaded_file) if uploaded_file else None
                try:
                    supabase.table("messages").insert({
                        "sender_id": st.session_state['user'].id,
                        "recipient_id": st.session_state['recipient_id'],
                        "content": message,
                        "image_url": image_url
                    }).execute()
                    # Message will be added via real-time subscription
                except Exception as e:
                    st.error(f"Failed to send message: {str(e)}")
            else:
                st.warning("Please enter a message or upload an image.")

# Main App Logic
def main():
    if not st.session_state['user']:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            login()
        with tab2:
            signup()
    else:
        chat_interface()

if __name__ == "__main__":
    main()