import os
import datetime
import uuid
import random

from flask import Flask, render_template, request, jsonify
from google.auth.transport import requests
import google.oauth2.id_token
from google.cloud import spanner

firebase_request_adapter = requests.Request()

app = Flask(__name__)

spanner_client = spanner.Client()

# instance_id = os.environ.get('SPANNER_INSTANCE')
# database_id = os.environ.get('SPANNER_DATABASE')

instance_id = 'chat-web-app-instance'
database_id = 'org-db'

global_thread_id = '00000000-00000000-00000000-00000000'

def get_user_by_name(name):
    sql_query_user = u"SELECT * FROM Users WHERE Name='{}'".format(name)
    database = spanner_client.instance(instance_id).database(database_id)
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(sql_query_user)

        for row in results:
            # print(row)
            return { 'Name': row[1], 'Email': row[2] }

    return None

def db_get_user(user_id):
    sql_query_user = u"SELECT * FROM Users WHERE UserId='{}'".format(user_id)
    database = spanner_client.instance(instance_id).database(database_id)
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(sql_query_user)

        for row in results:
            # print(row)
            return { 'Name': row[1], 'Email': row[2] }

    return None

def db_create_user(user_id, name, email):
    print(u'db_create_user {}, {}, {}'.format(user_id, name, email))
    def try_create_user(transaction):
        sql_create_user = u"INSERT INTO Users (UserId, Name, Email) VALUES ('{0}', '{1}', '{2}')" \
        .format(user_id, name, email)
        row_ct = transaction.execute_update(sql_create_user)
        print("{} record(s) inserted.".format(row_ct))
        personal_thread_id = str(uuid.uuid4())
        insert_thread(transaction, personal_thread_id, user_id, name, [name])
        sql_add_user_thread_membership = u"INSERT INTO ThreadMembership (UserId, ThreadId) " \
                                        "VALUES ('{0}','{1}')".format(user_id, global_thread_id)
        row_ct = transaction.execute_update(sql_add_user_thread_membership)

        sql_query_user = u"SELECT * FROM Users WHERE UserId='{}'".format(user_id)
        results = transaction.execute_sql(sql_query_user)
        for row in results:
            print(u"Created New User: {}, {}, {}".format(*row))
            return { 'Name': row[1], 'Email': row[2] }

    database = spanner_client.instance(instance_id).database(database_id)
    return database.run_in_transaction(try_create_user)



def get_user_threads(transaction, user_id):
    sql_get_current_threads = u"SELECT ThreadId FROM ThreadMembership WHERE UserId='{}'".format(user_id)
    query_result = transaction.execute_sql(sql_get_current_threads)
    #print("START :: " + user_id)
    threads = []
    for row in query_result:
        # print("row:" + str(row))
        for thread_id in row:
            #print("thread_id:" + str(thread_id))
            threads.append(thread_id)

    #print("threads: " + str(threads))
    return threads

def insert_thread(transaction, thread_id, creator_user_id, thread_name, thread_member_names):
    str_thread_member_names = str(thread_member_names).replace('[','(').replace(']',')')
    print(str_thread_member_names)
    sql_get_user_ids = u"SELECT UserId FROM Users WHERE Name IN {}".format(str_thread_member_names)
    results = transaction.execute_sql(sql_get_user_ids)
    
    thread_membership_values = ''
    for row in results:
        user_id = row[0]
        thread_membership_values += u"('{}', '{}'),".format(user_id, thread_id)

    # remove the last comma and carriage return
    if len(thread_membership_values) > 1:
        thread_membership_values = thread_membership_values[:-1]
    print(thread_membership_values)

    sql_create_thread = u"INSERT INTO Threads (ThreadId, CreatorId, TimeCreated, ThreadName) " \
                            "VALUES ('{}', '{}', PENDING_COMMIT_TIMESTAMP(), '{}')" \
                            .format(thread_id, creator_user_id, thread_name)
    row_ct = transaction.execute_update(sql_create_thread)

    sql_add_user_thread_membership = u"INSERT INTO ThreadMembership (UserId, ThreadId) " \
                                        "VALUES{}".format(thread_membership_values)
    
    print(sql_add_user_thread_membership)                                 
    row_ct = transaction.execute_update(sql_add_user_thread_membership)

    # print("{} record(s) inserted.".format(row_ct))
    # print("created new thread: " + thread_name)
    return jsonify({'status': ['Ok', 200], 'new_thread_id': thread_id })

def create_new_thread(creator_user_id, thread_name, thread_member_names):
    thread_id = str(uuid.uuid4())
    database = spanner_client.instance(instance_id).database(database_id)
    return database.run_in_transaction(insert_thread, thread_id, creator_user_id, thread_name, thread_member_names)

# new_thread_names = ['Michael Silk', 'fake_name_7065560', 'fake_name_50549095', 'fake_name_642872917']
# create_new_thread('XVJROmenIxRgF0ce0tRzwKtzlVy2', 'plop', new_thread_names)


def list_threads(user_id):
    def get_threads(transaction):
        thread_ids = get_user_threads(transaction, user_id)
        # if no threads are found for the user early out and return an empty list
        if len(thread_ids) == 0:
            return jsonify([])

        str_thread_ids = str(thread_ids).replace('[','(').replace(']',')')
        results = transaction.execute_sql(u"SELECT ThreadId, ThreadName FROM Threads WHERE ThreadId IN {} ORDER BY TimeCreated ASC".format(str_thread_ids))

        thread_names = []

        for row in results:
            #print(str(row))
            thread_names.append({ 'thread_id':row[0], 'thread_name':row[1] })

        #print(str(thread_names))
        return jsonify(thread_names)

    database = spanner_client.instance(instance_id).database(database_id)
    return database.run_in_transaction(get_threads)

# print(str(list_threads('XVJROmenIxRgF0ce0tRzwKtzlVy2')))

def get_messages(user_id, thread_id):
    if not thread_id:
        thread_id = global_thread_id

    def list_messages(transaction):
        # verify that the user is a member of the thread before getting the messages
        user_thread_membership = get_user_threads(transaction, user_id)
        if thread_id in user_thread_membership:
            sql_list_messages = u"SELECT Messages.MessageId, Messages.Message, Users.Name, Messages.TimeCreated FROM Messages " \
                "INNER JOIN Users ON Messages.CreatorId = Users.UserId " \
                "WHERE Messages.ThreadId='{}' " \
                "ORDER BY TimeCreated ASC" \
                .format(thread_id)

            # print(sql_list_messages)
            results = transaction.execute_sql(sql_list_messages)

            messages = []
            for row in results:
                # print(row)
                messages.append({ 'message_id': row[0], 'message': row[1], 'creator': row[2], 'time_created': row[3] })
            for msg in messages:
                print(msg['message'])

            return messages
        else:
            return 'Forbidden', 403

    database = spanner_client.instance(instance_id).database(database_id)
    return database.run_in_transaction(list_messages)

def create_message(user_id, thread_id, message):
    if not thread_id:
        thread_id = global_thread_id

    def create_message(transaction):
        # verify that the user is a member of the thread before getting the messages
        user_thread_membership = get_user_threads(transaction, user_id)
        print('user_thread_membership: ' + str(user_thread_membership))
        if thread_id in user_thread_membership:
            sql_create_message = u"INSERT INTO Messages (ThreadId, MessageId, CreatorId, TimeCreated, Message)" \
                                    "VALUES ('{}', '{}', '{}', PENDING_COMMIT_TIMESTAMP(), '{}')" \
                                    .format(thread_id, str(uuid.uuid4()), user_id, message)
            row_ct = transaction.execute_update(sql_create_message)
            print("{} record(s) inserted.".format(row_ct))
            return 'Ok', 200
        else:
            return 'Forbidden', 403

    database = spanner_client.instance(instance_id).database(database_id)
    return database.run_in_transaction(create_message)