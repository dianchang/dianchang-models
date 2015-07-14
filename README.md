# dc-models

## Usage

Clone it as git submodule:

```sh
$ git submodule add git@github.com:dianchang/dianchang-models.git models
$ pip install -r models/requirements.txt
```

Init:

```py
from models import init_models

init_models(app)
```

`app` should has `DC_DOMAIN`, `ROOT_TOPIC_ID`, `DEFAULT_PARENT_TOPIC_ID`, `ELASTICSEARCH_HOST` and `ELASTICSEARCH_HOSTS` configs in addition to SQLAlchemy configs.

##Pull codes

```
$ git pull --recurse-submodules
```
