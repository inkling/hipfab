# Hipfab

Hipfab is a simple library for fabric that adds support for interfacing with hipchat inside of fabric deployment scripts. Inkling use it internally to make our deployments more transparent, and to make sure we can easily troubleshoot and verify each deployment.

## Hipchat Decorator 

The Hipchat Decorator allows you to make an arbitrary task send a message when it starts and completes, as well as sending an error message if the deploy fails.

### Usage

`fabfile.py`

    from hipchat import hipchat
    from fabric.api import run, env

    env.user = 'bill'
    
    @hipchat(alias='deploy_now')
    def deploy_my_thing():
        run('ls')
        
In the console:
  
    bash$ fab --list
    Available commands:

      deploy_my_thing
      deploy_now
      hipchat.check_room    Checks a HipChat room for a particular person's full name.
      hipchat.send          Send a message to a HipChat room. [:message[,room[,color[,notify[,failure]]]]].
      hipchat.send_message  Send a message to a HipChat room. [:message[,room[,color[,notify[,failure]]]]].

    bash$ fab deploy_now
    [Hipchat] Sending message: 'Started 'deploy_my_thing'.' to 'deployments' as user 'Fabric [bill]'.
    [localhost] local: ls
    fabfile.py
    [Hipchat] Sending message: 'Deployed 'deploy_my_thing'.' to 'deployments' as user 'Fabric [bill]'.

In the hipchat room:

![Deployed my thing? Oh boy!](https://git.inkling.com/martinis/hipfab/raw/master/README_1.png)

You can pass any arguments to the `HipchatTask` decorator you normally pass to the `task` decorator.

#### Arguments

  - `message` - the message to send. If none is provided, a message will be generated based on the function name or the `what` argument. (default: `None`)
  - `room` (default: `deployments`)
  - `color` One of "yellow", "red", "green", "purple", "gray", or "random" (default: `green`)
  - `notify` - whether or not to notify the room (default: `False`)
  - `hip_name` - the name prefix of the user that will post the message. Messages will show up with a sender of `%{hip_name} [%{your_username}]`. Note that Hipchat API requires the total text to be less than 15 characters. Hipfab will try to shorten your username, and if it's still over 15 characters, it'll just use the name `Fabric`. (default: `Fabric`). 
  - `function` - the function being decorated, used only if no message or `what` text is given. Not required. (default: `None`)
  - `failure` - if the given message is one of failure or not. Will automatically color the output message red and change the pre-generated message. (default: `False`)
  - `what` - the destination and type of deployment. For example, `what="apache to stable"` will result in a message of `Deployed apache to stable.` if successful, or `Failed to deploy apache to stable!` on failure. (default: `None`)
    - Note - the `what` argument can also be a `callable` that takes the same arguments as the task that is being decorated. This callable must return a string, and this string will be inserted into the HipChat message, enabling you to generate different messages based on command-line parameters.
  - `verb` - the action that is being performed. (default: `deploy`)
  - `rooms` - rooms to notify **in addition** to the `room` argument provided above. (default: `[]`)

HipChat can also be called as a `fab` task directly - perhaps if you want to run a whole bunch of deploy steps, then signal success or failure. Check `fab --list` for the exact syntax, but it's something like this:

    » fab hipchat.send:"Hello",testroom
    [Hipchat] Sending message: 'Hello' to 'testroom' as user 'Fabric [bill]'.
    
This way, you could run a whole bunch of Fabric tasks and then tell the deployments room about it, like so:

    » fab deploy_my_thing hipchat.send:"Deployed all the things on stable",deployments

## Check Room

You can also use Hipfab to check to see if someone is in a particular Hipchat room. This can be used to make sure that someone who is in charge of a deployment is online and ready to verify the deploymentst.

### Usage

`fabfile.py`

    from hipchat import check_room
    from fabric.api import run, env

    env.user = 'bill'

    @check_room('joe')
    def deploy_my_thing():
        run('ls')

If joe was in the room, the console output will look something like this:

    bash$ fab deploy_my_thing
    [Hipchat] 'joe' is present; continuing with deployment.
    [Hipchat] Sending message: 'Started 'deploy_my_thing'.' to 'deployments' as user 'Fabric [bill]'.
    [localhost] local: ls
    fabfile.py
    [Hipchat] Sending message: 'Deployed 'deploy_my_thing'.' to 'deployments' as user 'Fabric [bill]'.


and proceed like normal.

If he wasn't, you would see something like this:

![Oh no! Joe isn't in the room!](https://git.inkling.com/martinis/hipfab/raw/master/README_2.png)


#### Arguments
  - `people` - the people to check for. Takes either an iterable of usernames or a string of a single user. This argument is required. 
  - `room` - the room to send a message to if the check fails. Defaults to `deployments`.

## Notes

* There's a debug variable in `hipchat.py` that you can change. If you set that to true, the library won't actually send any messages, but will just print to the console what it would have sent, like so:

  `fabfile.py`
  ``` 
  from fabric.api import run, env
  import hipchat
  hipchat.DEBUG = True
  
  env.user = 'bill'
  
  @hipchat.hipchat
  def bar():
      run('ls')
  ```
  
  Console output
  
  ```
  bash $ fab bar
  [127.0.0.1:2222] Executing task 'bar'
  [Hipchat] (Not) Sending message: 'Started 'bar'.' to 'deployments' as user 'Fabric [bill]'.
  [127.0.0.1:2222] Executing task 'bar'
  fabfile.py
  [Hipchat] (Not) Sending message: 'Deployed 'bar'.' to 'deployments' as user 'Fabric [bill]'.
  ```

## Contributions

We welcome contributions. Please submit a pull request and we'll take a look at it.

## Credits

1. [Peter Sobot](https://github.com/psobot)
2. [Stephen Martinis](https://github.com/moowiz2020)

Uses the awesome [requests](http://docs.python-requests.org/en/latest/) library.