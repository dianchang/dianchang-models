from ._base import db
from .user import *
from .question import *
from .topic import *
from .answer import *
from .log import *


def init_models(app):
    from ._helpers import init_es

    db.init_app(app)
    db.config = {
        'DC_DOMAIN': app.config.get('DC_DOMAIN'),
        'CDN_HOST': app.config.get('CDN_HOST'),
        'ROOT_TOPIC_ID': app.config.get('ROOT_TOPIC_ID'),
        'PRODUCT_TOPIC_ID': app.config.get('PRODUCT_TOPIC_ID'),
        'ORGANIZATION_TOPIC_ID': app.config.get('ORGANIZATION_TOPIC_ID'),
        'POSITION_TOPIC_ID': app.config.get('POSITION_TOPIC_ID'),
        'SKILL_TOPIC_ID': app.config.get('SKILL_TOPIC_ID'),
        'PEOPLE_TOPIC_ID': app.config.get('PEOPLE_TOPIC_ID'),
        'OTHER_TOPIC_ID': app.config.get('OTHER_TOPIC_ID'),
        'NC_TOPIC_ID': app.config.get('NC_TOPIC_ID')
    }

    init_es(app.config.get('ELASTICSEARCH_HOSTS'))
