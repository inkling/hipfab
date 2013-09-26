#
#  hipchat.py
#
#  For details and documentation:
#  https://github.com/inkling/hipfab
#
#  Copyright 2013 Inkling Systems, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json
import os

import requests

from fabric.api import task, execute, env
from fabric.tasks import Task

CONFIG_FILE = os.path.expanduser('~/.hipfab.json')

# I tried making this with the global keyword, and it didn't work. Go figure...
class __HipfabConfig:
    def __init__(self):
        self.token = None

    def __call__(self):
        if not self.token:
            try:
                with open(CONFIG_FILE) as conf_f:
                    self.token = json.load(conf_f)['TOKEN']
            except IOError:
                print "Couldn't find hipfab config file."
                print "Put a json config file in this location (" + CONFIG_FILE + ", and hipfab will find it next time"
                print 'Read the README for more details'
                self.token = raw_input("Please enter the hipchat token now: ")
        return self.token

get_token = __HipfabConfig()

HIPCHAT_MESSAGE_URL = "https://api.hipchat.com/v1/rooms/message"
HIPCHAT_SHOW_URL = "https://api.hipchat.com/v1/rooms/show"
HIPCHAT_USER_URL = "https://api.hipchat.com/v1/users/show"
HIPCHAT_USERS_URL = "https://api.hipchat.com/v1/users/list"
DEBUG = True

class HipchatTask(Task):
    def __init__(self, func, *args, **kwargs):
        self.func, self.w_args = func, args
        super(HipchatTask, self).__init__(**kwargs)
        self.w_kwargs = kwargs

    def run(self, *args, **kwargs):
        orig = self.w_kwargs.get('verb', None)
        self.w_kwargs['verb'] = 'start'
        _send_message(function=self.func,
                     task_args=args,
                     task_kwargs=kwargs,
                     *self.w_args,
                     **self.w_kwargs)
        if orig:
            self.w_kwargs['verb'] = orig
        else:
            self.w_kwargs.pop('verb')
            
        try:
            r = execute(self.func, *args, **kwargs)
        except:
            _send_message(function=self.func,
                         failure=True,
                         task_args=args,
                         task_kwargs=kwargs,
                         *self.w_args,
                         **self.w_kwargs)
            raise
        _send_message(function=self.func,
                     task_args=args,
                     task_kwargs=kwargs,
                     *self.w_args,
                     **self.w_kwargs)
        return r

class HipchatCheckTask(HipchatTask):
    def run(self, *args, **kwargs):
        try:
            _check_room(task_name=self.name,
                        task_args=args,
                        task_kwargs=kwargs,
                        *self.w_args,
                        **self.w_kwargs)
        except RuntimeError, e:               
            _send_message(function=self.func, failure=True, notify=1, message=e)
            return
        return execute(self.func, *args, **kwargs)

def wrapper_hof(klass):
    def outer(*args, **kwds):
        invoked = bool(not args or kwds)

        def wrapper(func):
            rval = klass(func, *args, **kwds)
            rval.__name__   = rval.name = func.__name__
            rval.__doc__    = func.__doc__
            rval.__module__ = func.__module__
            return rval

        if not invoked:
            func, args = args[0], args[1:]
            return wrapper(func)
        else:
            return wrapper
    return outer

hipchat = wrapper_hof(HipchatTask)
checkroom = wrapper_hof(HipchatCheckTask)

@task
def check_room(*args, **kwargs):
    return _check_room(*args, **kwargs)

def _check_room(people, task_name, room="deployments", task_args=set(), task_kwargs={}):
    """ Checks a HipChat room for a particular person's full name.
        Syntax:  people,task_name[,room]"""
    if not room:
        raise RuntimeError("Need a room to check!")
    if not people:
        raise RuntimeError("Need specific people to check for!")
    if type(people) in (str, bytes):
        people = (people,)

    #A list of Full Names in the room.
    result = requests.get(HIPCHAT_SHOW_URL, params={
        'auth_token': get_token(),
        'room_id': room
    }).json()
    if 'error' in result:
        raise RuntimeError("Error when retrieving users in the room: \n%s" % json.dumps(result['error']['message'], indent=True))

    #A list of all HipChat users that we can use to match @mention names to Full Names
    users_res = requests.get(HIPCHAT_USERS_URL, params={
        'auth_token': get_token()
    }).json()
    if 'error' in users_res:
        raise RuntimeError("Error when retrieving all users: \n%s" % json.dumps(result['error']['message'], indent=True))

    allusers = users_res['users']
    mention_names = set(user['mention_name'].lower() for user in allusers)

    participants = [ res for res in result['room']['participants'] ]

    token = get_token()

    def filter_func(user):
        user_info = requests.get(HIPCHAT_USER_URL, params={
                'auth_token': token,
                'user_id': user['user_id'],
            }).json()
        if 'error' in result:
            raise RuntimeError("Error when retrieving info on a user: \n%s" % json.dumps(user_info['error']['message'], indent=True))
        return user_info['user']['status'] == u'available'

    participants = [part['name'].lower() for part in participants if filter_func(part)]

    #Go through list of acceptable DRIs and make sure at least one is in the room
    for person in people:
        if person.lower() not in mention_names:
            raise Exception("Person %s is not a valid HipChat user" % (person))

        for user in allusers:
            if user['mention_name'] == person:
                user_object = user
                break

        person_fullname = user_object['name'].lower()

        if person_fullname in participants:
            #We're good! 
            print "[Hipchat] '%s' is present; continuing with deployment." % user_object['mention_name']
            return

    err = "%s: Not deploying, could not find Verification DRIs in room %s: %s"%(task_name, room, str(["@%s" % person for person in people]))
    raise RuntimeError(err)

check_room.__doc__ = _check_room.__doc__

@task(alias='send')
def send_message(*args, **kwargs):
    return _send_message(*args, **kwargs)

def _send_message(message=None,
                 room='deployments',
                 color='green',
                 message_format='text',
                 notify=False,
                 failure=False,
                 hip_name='Fabric',
                 function=None,
                 what=None,
                 verb='deploy',
                 rooms=[],
                 people=None, 
                 task_args=set(),
                 task_kwargs={},
                 **_kwargs):
    """
    Send a message to a HipChat room. [:message[,room[,color[,notify[,failure]]]]].
    Specify a 'rooms' argument to add additional rooms to be notified.
    """
    #   "what" for nicer decorator application
    if not message:
        if not what:
            if function is not None:
                what = "'%s'" % function.__name__
            else:
                raise RuntimeError("No message or function provided!")

        if not failure:
            prefix = verb.capitalize() + "ed"
        else:
            prefix = "Failed to %s" % verb

        for remove in ['hosts', 'roles', 'exclude_hosts']:
            task_kwargs.pop(remove, False)

        if callable(what):
            try:
                thing = what(*task_args, **task_kwargs)
            except TypeError:
                print "Lambda specified has mismatching arguments."
                thing = "<unknown>"
        else:
            thing = what
        message = "%s %s." % (prefix, thing)

    formatted = "[%s]" % env.user
    new_name = hip_name + " " + formatted

    #The hipchat API limits the username to 15 characters.... :/
    if len(new_name) > 15 and hip_name == 'Fabric': #We can shorten 'Fabric'
        new_name = 'Fab ' + formatted
    if len(new_name) > 15:
        new_name = hip_name
    if len(new_name) > 15:
        new_name = formatted
    if len(new_name) > 15:
        print "Get a shorter username! %s is longer than 15 characters" % new_name
        print "Using 'Fabric' for now."
        new_name = 'Fabric'
    name = new_name

    for room in set(rooms + [room]):
        print "[Hipchat] %s message: '%s' to '%s' as user '%s'." % \
            ("Sending" if not DEBUG else "(Not) Sending", message, room, name)
        if not DEBUG:
            resp = requests.get(HIPCHAT_MESSAGE_URL, params={
                'auth_token': get_token(),
                'room_id': room,
                'from': name,
                'color': color if not failure else 'red',
                'message': message,
                'message_format': message_format,
                'notify': notify,
            })
            if resp.json() != {u'status' : u'sent'}:
                print 'Sending failed:'
                print json.dumps(resp.json(), indent=True)

send_message.__doc__ = _send_message.__doc__
