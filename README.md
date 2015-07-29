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

`app` should have configs as follows:

```py
SQLALCHEMY_BINDS = {
    'dc': "mysql+pymysql://root:@localhost/dianchang"
}
ROOT_TOPIC_ID = 1
PRODUCT_TOPIC_ID = 2
ORGANIZATION_TOPIC_ID = 3
POSITION_TOPIC_ID = 4
SKILL_TOPIC_ID = 5
PEOPLE_TOPIC_ID = 6
OTHER_TOPIC_ID = 7
NC_TOPIC_ID = 8
CDN_HOST = "http://xxx.qiniudn.com"
DC_DOMAIN = "http://127.0.0.1"
ELASTICSEARCH_HOSTS = [{"host": "localhost", "port": 9200}]
```

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
