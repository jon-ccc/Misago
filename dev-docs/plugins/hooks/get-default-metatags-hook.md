# `get_default_metatags_hook`

This hook wraps the standard function that Misago uses to get default metatags for all pages.


## Location

This hook can be imported from `misago.metatags.hooks`:

```python
from misago.metatags.hooks import get_default_metatags_hook
```


## Filter

```python
def custom_get_default_metatags_filter(
    action: GetDefaultMetatagsHookAction, request: HttpRequest
) -> dict[str, MetaTag]:
    ...
```

A function implemented by a plugin that can be registered in this hook.


### Arguments

#### `action: GetDefaultMetatagsHookAction`

Misago function used to get default metatags for all pages.

See the [action](#action) section for details.


#### `request: HttpRequest`

The request object.


### Return value

A Python `dict` with metatags to include in the response HTML.


## Action

```python
def get_default_metatags_action(request: HttpRequest) -> dict[str, MetaTag]:
    ...
```

Misago function used to get default metatags for all pages.


### Arguments

#### `request: HttpRequest`

The request object.


### Return value

A Python `dict` with metatags to include in the response HTML.


## Example

The code below implements a custom filter function that adds a custom metatag to all pages:

```python
from django.http import HttpRequest
from misago.metatags.hooks import get_default_metatags_hook
from misago.metatags.metatag import MetaTag


@get_default_metatags_hook.append_filter
def include_custom_metatag(action, request: HttpRequest) -> dict[str, MetaTag]:
    metatags = action(request)
    metatags["custom"] = MetaTag(
        name="og:custom",
        property="twitter:custom",
        itemprop="custom",
        content="custom content",
    )
    return metatags
```