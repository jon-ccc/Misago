# `get_threads_users_hook`

This hook wraps the standard function that Misago uses to get `User` objects to display on threads list.


## Location

This hook can be imported from `misago.threads.hooks`:

```python
from misago.threads.hooks import get_threads_users_hook
```


## Filter

```python
def custom_get_threads_users_filter(
    action: GetThreadsUsersHookAction,
    request: HttpRequest,
    threads: list[Thread],
) -> dict[int, 'User']:
    ...
```

A function implemented by a plugin that can be registered in this hook.


### Arguments

#### `action: GetThreadsUsersHookAction`

Next function registered in this hook, either a custom function or Misago's standard one.

See the [action](#action) section for details.


#### `request: HttpRequest`

The request object.


#### `threads: list[Thread]`

A Python list with `Thread` instances to pull starters and last posters for.


### Return value

A Python `dict` with `User` instances.


## Action

```python
def get_threads_users_action(request: HttpRequest, threads: list[Thread]) -> dict[int, 'User']:
    ...
```

Misago function used to get `User` objects to display on threads list.


### Arguments

#### `request: HttpRequest`

The request object.


#### `threads: list[Thread]`

A Python list with `Thread` instances to pull starters and last posters for.


### Return value

A Python `dict` with `User` instances.


## Example

The code below implements a custom filter function that excludes users hidden by the plugin from the threads list:

```python
from django.http import HttpRequest

from misago.threads.hooks import get_threads_users_hook
from misago.threads.models import Thread
from misago.users.models import User


@get_threads_users_hook.append_filter
def exclude_hidden_users(
    action, request: HttpRequest, threads: list[Thread]
) -> dict[int, User]:
    users = action(request, threads)

    for thread in threads:
        hidden_user_id = thread.plugin_data.get("hidden_user_id")
        if hidden_user_id and hidden_user_id in users:
            del users[hidden_user_id]

    return users
```