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

`app` should has `DC_DOMAIN`, `ROOT_TOPIC_ID`, `DEFAULT_PARENT_TOPIC_ID` and `ELASTICSEARCH_HOSTS` configs in addition to SQLAlchemy configs.

##Pull latest codes

```
$ git submodule foreach git checkout master
$ git submodule foreach git pull origin master
```

##Clone

```
$ git clone xxx.git --recursive
```

If you already cloned but forgot --recursive, you can also fetch submodules with `git submodule update --init`.
