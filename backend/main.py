import os
import datetime
import uuid
import random
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from google.auth.transport import requests
import google.oauth2.id_token
from database import db_get_user, db_create_user, create_new_thread, list_threads, get_messages, create_message, get_user_by_name

firebase_request_adapter = requests.Request()

app = Flask(__name__)
app.config.from_object(__name__)
# enable CORS
CORS(app, resources={r'/*': {'origins': '*'}})

@app.route('/user', methods=['GET'])
def get_user():
    id_token = request.headers['Authorization']
    error_message = None
    claims = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            # TODO: cache results in an encrypted session store.
            # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)

            uid = claims['sub']

            return db_get_user(uid)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)
            return error_message
            
    return 'id token not valid: ' + id_token

@app.route('/user', methods=['POST'])
def create_user():
    print('create_user')
    id_token = request.headers['Authorization']
    data = request.get_json()
    print('Json Args: ' + str(jsonify(request.args)))
    print('Json Args: ' + str(data))
    if 'username' in data:
        username = data['username']
    else:
        return ValueError('Invalid Argument: "username" was not specified')

    print('Create User: ' + username)
    error_message = None
    claims = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            # TODO: cache results in an encrypted session store.
            # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)

            uid = claims['sub']
            email = claims['email']

            return db_create_user(uid, username, email)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)
            return error_message
            
    return 'id token not valid: ' + id_token 

# @app.route('/users', methods=['GET'])
# def get_users():
#     id_token = request.headers['Authorization']
#     error_message = None
#     claims = None

#     if id_token:
#         try:
#             # Verify the token against the Firebase Auth API.
#             # TODO: cache results in an encrypted session store.
#             # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
#             claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)

#             uid = claims['sub']
#             if 'name' in claims:
#                 name = claims['name']
#             else:
#                 name = 'na'

#             return get_or_create_user(uid, name, claims['email'])

#         except ValueError as exc:
#             # This will be raised if the token is expired or any other
#             # verification checks fail.
#             error_message = str(exc)

#     return error_message

@app.route('/threads', methods=['GET'])
def threads():
    id_token = request.headers['Authorization']
    error_message = None
    claims = None
    # times = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            # TODO: cache results in an encrypted session store.
            # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            uid = claims['sub']

            return list_threads(uid)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)
    return error_message

@app.route('/threads', methods=['POST'])
def create_thread():
    id_token = request.headers['Authorization']
    error_message = None
    claims = None
    # times = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            # TODO: cache results in an encrypted session store.
            # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            uid = claims['sub']

            data = request.get_json()
            thread_name = data['thread_name']
            thread_members = data['thread_members']
            print(thread_name + " :: " + str(thread_members))
            return create_new_thread(uid, thread_name, thread_members)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)
    return error_message

# returns a list of messages for a given thread
@app.route('/messages', methods=['GET'])
def messages():
    id_token = request.headers['Authorization']
    thread_id = None
    if 'thread_id' in request.args:
        thread_id = request.args.get('thread_id')

    print('Get Messages: ' + str(thread_id))
    error_message = None
    claims = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            # TODO: cache results in an encrypted session store.
            # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            uid = claims['sub']
            messages = get_messages(uid, thread_id)
            return jsonify(messages)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)
    return error_message


@app.route('/messages', methods=['POST', 'PUT'])
def add_message():
    id_token = request.headers['Authorization']
    thread_id = None
    if 'thread_id' in request.args:
        thread_id = request.args.get('thread_id')
    error_message = None
    claims = None
    # times = None

    if id_token:
        try:
            # Verify the token against the Firebase Auth API.
            # TODO: cache results in an encrypted session store.
            # See http://flask.pocoo.org/docs/1.0/quickstart/#sessions.
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_id = claims['sub']

            data = request.get_json()
            #thread_id = data['thread_id']
            message = data['message']
            print(message)
            return create_message(user_id, thread_id, message)

        except ValueError as exc:
            # This will be raised if the token is expired or any other
            # verification checks fail.
            error_message = str(exc)
    
    return error_message

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=5000, debug=True)
