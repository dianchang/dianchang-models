# coding: utf-8
import json
from datetime import datetime
from ._base import db
from ._helpers import pinyin, get_pure_content, save_object_to_es, delete_object_from_es, search_objects_from_es


class Topic(db.Model):
    """话题"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    name_pinyin = db.Column(db.String(100))
    wiki = db.Column(db.Text(4294967295))
    wiki_preview = db.Column(db.Text)
    avatar = db.Column(db.String(200), default='default_topic_avatar.png')
    clicks = db.Column(db.Integer, default=0)
    root = db.Column(db.Boolean, default=False)
    kind = db.Column(db.Integer)  # 类型 1：产品，2：组织，3：职业，4：技能，5：人名，6：其他
    other_kind = db.Column(db.String(100))  # 其他类型
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now)  # 该话题下有新问题或新回答时，更新此字段

    all_locked = db.Column(db.Boolean, default=False)  # 全部锁定
    name_locked = db.Column(db.Boolean, default=False)  # 锁定名称
    avatar_locked = db.Column(db.Boolean, default=False)  # 锁定图片
    wiki_locked = db.Column(db.Boolean, default=False)  # 锁定百科
    parent_topics_locked = db.Column(db.Boolean, default=False)  # 锁定所属话题
    child_topics_locked = db.Column(db.Boolean, default=False)  # 锁定下属话题
    merge_topic_locked = db.Column(db.Boolean, default=False)  # 锁定合并话题
    topic_kind_locked = db.Column(db.Boolean, default=False)  # 锁定话题类型

    # 用于话题热度计算
    avg = db.Column(db.Float, default=0)  # 均值
    sqrt_avg = db.Column(db.Float, default=0)  # 平方和均值
    hot_score = db.Column(db.Float, default=0)  # 热度
    hide_from_hot = db.Column(db.Boolean, default=0)  # 不在热议话题中显示

    followers_count = db.Column(db.Integer, default=0)
    questions_count = db.Column(db.Integer, default=0)  # 问题数量
    all_questions_count = db.Column(db.Integer, default=0)  # 问题数量（包含子话题下的问题）

    # 合并至话题
    merge_to_topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    merge_to_topic = db.relationship('Topic', remote_side=[id])

    def __setattr__(self, name, value):
        """为name赋值时，自动设置其拼音"""
        if name == 'name':
            super(Topic, self).__setattr__('name_pinyin', pinyin(value))
        if name == 'wiki':
            pure_content = get_pure_content(value)
            if len(pure_content) > 100:
                wiki_preview = pure_content[:100].rstrip('.')
            else:
                wiki_preview = pure_content
            super(Topic, self).__setattr__('wiki_preview', wiki_preview)
        super(Topic, self).__setattr__(name, value)

    @property
    def avatar_url(self):
        """话题图像"""
        return "%s/%s?imageView2/1/w/160" % (db.config.get('CDN_HOST'), self.avatar)

    def followed_by_user(self, user_id):
        """此话题是否被用户关注"""
        return FollowTopic.query.filter(FollowTopic.topic_id == self.id, FollowTopic.user_id == user_id).count() > 0

    def experience_from_user(self, user_id):
        """当前用户在该话题下的话题经验"""
        statistic = UserTopicStatistic.query.filter(UserTopicStatistic.user_id == user_id,
                                                    UserTopicStatistic.topic_id == self.id).first()
        if statistic:
            return statistic.experience
        else:
            return None

    @property
    def ancestor_paths(self):
        """寻找根话题到该话题之间的所有路径"""
        ROOT_TOPIC_ID = db.config.get('ROOT_TOPIC_ID')
        ancestor_topics_id_list = self.ancestor_topics_id_list[:]
        all_list = ancestor_topics_id_list[:]
        all_list.append(self.id)

        nodes = {}
        for ancestor_topic_id in ancestor_topics_id_list:
            ancestor_topic = Topic.query.get_or_404(ancestor_topic_id)
            child_topics_id_list = ancestor_topic.child_topics_id_list
            nodes[ancestor_topic_id] = _intersect_list(child_topics_id_list, all_list)
        paths = Topic.find_all_paths(nodes, ROOT_TOPIC_ID, self.id)

        topic_paths = []
        for path in paths:
            topic_path = Topic.query.filter(Topic.id.in_(path))
            topic_paths.append(topic_path)
        return topic_paths

    def save_to_es(self):
        """保存此话题到elasticsearch"""
        synonyms = []
        for synonym in self.synonyms:
            synonyms.append(synonym.synonym)
            synonyms.append(synonym.synonym_pinyin)

        return save_object_to_es('topic', self.id, {
            'name': self.name,
            'name_pinyin': self.name_pinyin,
            'synonyms': synonyms,
            'created_at': self.created_at
        })

    def delete_from_es(self):
        """从elasticsearch中删除此话题"""
        return delete_object_from_es('topic', self.id)

    @staticmethod
    def query_from_es(q, page=1, per_page=10, only_id_list=False):
        """在elasticsearch中查询话题"""
        results = search_objects_from_es(doc_type='topic', body={
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["name", "name_pinyin", "synonyms"]
                }
            },
            "highlight": {
                "fields": {
                    "name": {}
                }
            },
            "from": per_page * (page - 1),
            "size": per_page
        })

        result_topics = []

        if only_id_list:
            for result in results["hits"]["hits"]:
                id = result["_id"]
                result_topics.append(id)
            return result_topics

        for result in results["hits"]["hits"]:
            id = result["_id"]
            topic = Topic.query.get(id)
            if "highlight" in result:
                if "name" in result["highlight"]:
                    topic.highlight_name = result["highlight"]["name"][0]
            result_topics.append(topic)

        return result_topics, results["hits"]["total"], results['took']

    @staticmethod
    def get_by_name(name, user_id=None, create_if_not_exist=False):
        """通过name获取句集"""
        from .log import PublicEditLog, TOPIC_EDIT_KIND

        NC_TOPIC_ID = db.config.get('NC_TOPIC_ID')

        name = name or ""
        name = name.strip()
        if name:
            # 若不存在该name的句集，则创建
            topic = Topic.query.filter(Topic.name == name).first()
            if not topic and create_if_not_exist:
                topic = Topic(name=name)
                db.session.add(topic)
                db.session.commit()

                # Add topic closure
                topic_closure = TopicClosure(ancestor_id=topic.id, descendant_id=topic.id, path_length=0)
                db.session.add(topic_closure)

                # Create topic log
                log = PublicEditLog(kind=TOPIC_EDIT_KIND.CREATE, user_id=user_id, after=name, after_id=topic.id,
                                    original_name=topic.name)
                topic.logs.append(log)
                db.session.add(topic)
                db.session.commit()

                topic.save_to_es()  # save to elasticsearch
                topic.add_parent_topic(NC_TOPIC_ID)
            return topic
        else:
            return None

    @property
    def all_questions(self):
        """该话题下的所有问题（包括直接子话题的问题）"""
        from .question import QuestionTopic, Question

        # topics_id_list = self.descendant_topics_id_list
        topics_id_list = self.child_topics_id_list
        topics_id_list.append(self.id)
        return Question.query.filter(Question.topics.any(QuestionTopic.topic_id.in_(
            topics_id_list))).order_by(Question.created_at.desc())

    @property
    def all_answers(self):
        """该话题下的所有问题回答（包括直接子话题的问题回答）"""
        from .answer import Answer
        from .question import Question, QuestionTopic

        # topics_id_list = self.descendant_topics_id_list
        topics_id_list = self.child_topics_id_list
        topics_id_list.append(self.id)
        return Answer.query.filter(Answer.question.has(Question.topics.any(
            QuestionTopic.topic_id.in_(topics_id_list))))

    @property
    def answers(self):
        """topic.questions 下的所有回答"""
        from .answer import Answer
        from .question import Question, QuestionTopic

        return Answer.query.filter(Answer.question.has(Question.topics.any(
            QuestionTopic.topic_id == self.id)))

    @property
    def parent_topics_id_list(self):
        """直接父话题id列表"""
        parent_topics_id_list = db.session.query(TopicClosure.ancestor_id). \
            filter(TopicClosure.descendant_id == self.id,
                   TopicClosure.ancestor_id != self.id,
                   TopicClosure.path_length == 1). \
            all()
        return _remove_repeats_from_list([item.ancestor_id for item in parent_topics_id_list])

    @property
    def parent_topics(self):
        """直接父话题"""
        parent_topics_id_list = self.parent_topics_id_list
        return Topic.query.filter(Topic.id.in_(parent_topics_id_list))

    @property
    def ancestor_topics_id_list(self):
        """祖先话题id列表"""
        ancestor_topics_id_list = db.session.query(TopicClosure.ancestor_id). \
            filter(TopicClosure.descendant_id == self.id,
                   TopicClosure.ancestor_id != self.id). \
            all()

        return _remove_repeats_from_list([item.ancestor_id for item in ancestor_topics_id_list])

    @property
    def ancestor_topics(self):
        """祖先话题"""
        return Topic.query.filter(Topic.id.in_(self.ancestor_topics_id_list))

    @property
    def child_topics_id_list(self):
        """直接子话题id列表"""
        child_topics_id_list = db.session.query(TopicClosure.descendant_id). \
            filter(TopicClosure.ancestor_id == self.id,
                   TopicClosure.descendant_id != self.id,
                   TopicClosure.path_length == 1). \
            all()
        return _remove_repeats_from_list([item.descendant_id for item in child_topics_id_list])

    @property
    def child_topics(self):
        """直接子话题"""
        return Topic.query.filter(Topic.id.in_(self.child_topics_id_list))

    @property
    def descendant_topics_id_list(self):
        """子孙话题id列表"""
        descendant_topics_id_list = db.session.query(TopicClosure.descendant_id). \
            filter(TopicClosure.ancestor_id == self.id,
                   TopicClosure.descendant_id != self.id).all()
        return _remove_repeats_from_list([item.descendant_id for item in descendant_topics_id_list])

    @property
    def descendant_topics(self):
        """子孙话题"""
        return Topic.query.filter(Topic.id.in_(self.descendant_topics_id_list))

    @staticmethod
    def other_topics():
        """其他话题，包括 人、其他、未分类 话题下的所有子话题"""
        NC_TOPIC_ID = db.config.get('NC_TOPIC_ID')
        OTHER_TOPIC_ID = db.config.get('OTHER_TOPIC_ID')
        PEOPLE_TOPIC_ID = db.config.get('PEOPLE_TOPIC_ID')
        descendant_topics = db.session.query(TopicClosure.descendant_id). \
            filter(TopicClosure.ancestor_id.in_([NC_TOPIC_ID, OTHER_TOPIC_ID, PEOPLE_TOPIC_ID]),
                   TopicClosure.descendant_id != TopicClosure.ancestor_id).all()
        descendant_topics_id_list = [item.descendant_id for item in descendant_topics]
        return Topic.query.filter(Topic.id.in_(descendant_topics_id_list))

    def add_parent_topic(self, parent_topic_id):
        """添加直接父话题"""
        for ancestor_topic in TopicClosure.query.filter(TopicClosure.descendant_id == parent_topic_id):
            for descendant_topic in TopicClosure.query.filter(TopicClosure.ancestor_id == self.id):
                new_closure = TopicClosure(ancestor_id=ancestor_topic.ancestor_id,
                                           descendant_id=descendant_topic.descendant_id,
                                           path_length=ancestor_topic.path_length + descendant_topic.path_length + 1)
                db.session.add(new_closure)
        db.session.commit()

    def remove_parent_topic(self, parent_topic_id):
        """删除直接父话题"""
        print("%d-%d" % (self.id, parent_topic_id))
        for ancestor_topic in TopicClosure.query.filter(TopicClosure.descendant_id == parent_topic_id):
            for descendant_topic in TopicClosure.query.filter(TopicClosure.ancestor_id == self.id):
                closure = TopicClosure.query. \
                    filter(TopicClosure.ancestor_id == ancestor_topic.ancestor_id,
                           TopicClosure.descendant_id == descendant_topic.descendant_id,
                           TopicClosure.path_length == ancestor_topic.path_length + descendant_topic.path_length + 1). \
                    first()
                if closure:
                    db.session.delete(closure)
        db.session.commit()

    def add_child_topic(self, child_topic_id, from_merge=False):
        """添加直接子话题"""
        for ancestor_topic in TopicClosure.query.filter(TopicClosure.descendant_id == self.id):
            for descendant_topic in TopicClosure.query.filter(TopicClosure.ancestor_id == child_topic_id):
                new_closure = TopicClosure(ancestor_id=ancestor_topic.ancestor_id,
                                           descendant_id=descendant_topic.descendant_id,
                                           path_length=ancestor_topic.path_length + descendant_topic.path_length + 1,
                                           from_merge=from_merge)
                db.session.add(new_closure)
        db.session.commit()

    def remove_child_topic(self, child_topic_id, from_merge=False):
        """删除直接子话题"""
        for ancestor_topic in TopicClosure.query.filter(TopicClosure.descendant_id == self.id):
            for descendant_topic in TopicClosure.query.filter(TopicClosure.ancestor_id == child_topic_id):
                closure = TopicClosure.query. \
                    filter(TopicClosure.ancestor_id == ancestor_topic.ancestor_id,
                           TopicClosure.descendant_id == descendant_topic.descendant_id,
                           TopicClosure.path_length == ancestor_topic.path_length + descendant_topic.path_length + 1)
                if from_merge:
                    closure = closure.filter(TopicClosure.from_merge)
                closure = closure.first()
                if closure:
                    db.session.delete(closure)
        db.session.commit()

    @staticmethod
    def find_min_path(topic_id_a, topic_id_b):
        """寻找话题之间的最短路径长度"""
        path = db.session.query(db.func.min(TopicClosure.path_length).label("min_path")).filter(db.or_(
            db.and_(TopicClosure.ancestor_id == topic_id_a, TopicClosure.descendant_id == topic_id_b),
            db.and_(TopicClosure.descendant_id == topic_id_a, TopicClosure.ancestor_id == topic_id_b))).first()
        return path.min_path

    @staticmethod
    def find_all_paths(graph, start, end, path=[]):
        """获取图中节点A到节点B的所有路径

        见：
        https://www.python.org/doc/essays/graphs/
        http://devres.zoomquiet.io/data/20071011232111/index.html
        """
        path = path + [start]
        if start == end:
            return [path]
        if not graph.has_key(start):
            return []
        paths = []
        for node in graph[start]:
            if node not in path:
                newpaths = Topic.find_all_paths(graph, node, end, path)
                for newpath in newpaths:
                    paths.append(newpath)
        return paths

    def __repr__(self):
        return '<Topic %s>' % self.name


class TopicClosure(db.Model):
    """话题的closure table

    见：
    https://www.percona.com/blog/2011/02/14/moving-subtrees-in-closure-table/
    《SQL反模式》http://book.douban.com/subject/6800774/
    """
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    from_merge = db.Column(db.Boolean, default=False)
    ancestor_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    descendant_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    path_length = db.Column(db.Integer)

    def __repr__(self):
        return '<TopicClosure %d-%d>' % (self.ancestor_id, self.descendant_id)


class TopicSynonym(db.Model):
    """话题同义词"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    from_merge = db.Column(db.Boolean, default=False)
    synonym = db.Column(db.String(200))
    synonym_pinyin = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic', backref=db.backref('synonyms',
                                                        lazy='dynamic',
                                                        order_by='desc(TopicSynonym.created_at)'))

    def __setattr__(self, name, value):
        """为synonym赋值时，自动设置其拼音"""
        if name == 'synonym':
            super(TopicSynonym, self).__setattr__('synonym_pinyin', pinyin(value))
        super(TopicSynonym, self).__setattr__(name, value)


class FollowTopic(db.Model):
    """关注话题"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    from_merge = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic', backref=db.backref('followers',
                                                        lazy='dynamic',
                                                        order_by='desc(FollowTopic.created_at)'))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('followed_topics',
                                                      lazy='dynamic',
                                                      order_by='desc(FollowTopic.created_at)'))

    def __repr__(self):
        return '<FollowQuestion %s>' % self.id


class WorkOnProduct(db.Model):
    """工作过的产品"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    current = db.Column(db.Boolean, default=False)  # 是否当前在职
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic', backref=db.backref('workers',
                                                        lazy='dynamic',
                                                        order_by='desc(WorkOnProduct.created_at)'))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('products_worked_on',
                                                      lazy='dynamic',
                                                      order_by='asc(WorkOnProduct.created_at)'))

    def __repr__(self):
        return '<WorkOnProduct %s>' % self.id


class TopicWikiContributor(db.Model):
    """话题Wiki贡献者"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, default=0)
    last_contributed_at = db.Column(db.DateTime, default=datetime.now)
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic', backref=db.backref('wiki_contributors',
                                                        lazy='dynamic',
                                                        order_by='desc(TopicWikiContributor.count)'))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('contributed_topics',
                                                      lazy='dynamic',
                                                      order_by='desc(TopicWikiContributor.count)'))


class UserTopicStatistic(db.Model):
    """话题统计

    记录用户在某话题下的数据。
    """
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    answers_count = db.Column(db.Integer, default=0)  # 用户在该话题下的回答数
    upvotes_count = db.Column(db.Integer, default=0)  # 用户在该话题下收获的赞同数
    score = db.Column(db.Integer, default=0)  # 用户对该话题的擅长度
    selected = db.Column(db.Boolean, default=False)  # 是否选择该话题作为擅长话题
    worked_on = db.Column(db.Boolean, default=False)  # 是否曾经工作过
    show_order = db.Column(db.Integer, default=0)  # 擅长话题排列顺序（越大越排在后面）
    experience = db.Column(db.String(200))  # 话题经验
    week_answers_count = db.Column(db.String(200))  # 近7天的回答数，以数组的 json 形式存入，例如：[1,2,3,4,5,6,7]，越往左天数越早
    week_upvotes_count = db.Column(db.String(200))  # 近7天的赞同数，格式同上
    week_score = db.Column(db.Float, default=0)  # 近7天的表现得分
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')

    @staticmethod
    def add_answer_in_topic(user_id, topic_id):
        """在某话题下回答"""
        topic_expert = UserTopicStatistic.query.filter(
            UserTopicStatistic.topic_id == topic_id,
            UserTopicStatistic.user_id == user_id).first()
        if topic_expert:
            topic_expert.answers_count += 1
        else:
            topic_expert = UserTopicStatistic(topic_id=topic_id, user_id=user_id, answers_count=1, upvotes_count=0)
        topic_expert.calculate_score()
        db.session.add(topic_expert)
        db.session.commit()

    @staticmethod
    def remove_answer_from_topic(user_id, topic_id):
        """从某话题中移除回答"""
        topic_expert = UserTopicStatistic.query.filter(UserTopicStatistic.topic_id == topic_id,
                                                       UserTopicStatistic.user_id == user_id).first()
        if topic_expert:
            if topic_expert.answers_count > 0:
                topic_expert.answers_count -= 1
            else:
                topic_expert.answers_count = 0
        else:
            topic_expert = UserTopicStatistic(topic_id=topic_id, user_id=user_id, answers_count=0, upvotes_count=0)
        topic_expert.calculate_score()
        db.session.add(topic_expert)
        db.session.commit()

    @staticmethod
    def upvote_answer_in_topic(user_id, topic_id, count=1):
        """在该话题下赞同该用户"""
        topic_expert = UserTopicStatistic.query.filter(UserTopicStatistic.topic_id == topic_id,
                                                       UserTopicStatistic.user_id == user_id).first()
        if topic_expert:
            topic_expert.upvotes_count += count
        else:
            topic_expert = UserTopicStatistic(topic_id=topic_id, user_id=user_id, upvotes_count=count, answers_count=0)
        topic_expert.calculate_score()
        db.session.add(topic_expert)
        db.session.commit()

    @staticmethod
    def cancel_upvote_answer_in_topic(user_id, topic_id, count=1):
        """取消在该话题下对该用户的赞同"""
        topic_expert = UserTopicStatistic.query.filter(UserTopicStatistic.topic_id == topic_id,
                                                       UserTopicStatistic.user_id == user_id).first()
        if topic_expert:
            if topic_expert.upvotes_count >= count:
                topic_expert.upvotes_count -= count
            else:
                topic_expert.upvotes_count = 0
        else:
            topic_expert = UserTopicStatistic(topic_id=topic_id, user_id=user_id, answers_count=0, upvotes_count=0)
        topic_expert.calculate_score()
        db.session.add(topic_expert)
        db.session.commit()

    def calculate_score(self):
        """计算擅长度"""
        self.score = self.answers_count + self.upvotes_count

    def calculate_week_score(self):
        """计算近7天的得分"""
        score = 0

        week_answers_count = json.loads(self.week_answers_count)
        for count in week_answers_count:
            score += count

        week_upvotes_count = json.loads(self.week_upvotes_count)
        for count in week_upvotes_count:
            score += count

        self.week_score = score


class ApplyTopicDeletion(db.Model):
    """申请删除话题"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')


class RelevantTopic(db.Model):
    """相关话题"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic',
                            backref=db.backref('relevant_topics',
                                               lazy='dynamic',
                                               order_by='desc(RelevantTopic.score)'),
                            foreign_keys=[topic_id])

    relevant_topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    relevant_topic = db.relationship('Topic', foreign_keys=[relevant_topic_id])


def _intersect_list(a, b):
    """求列表的并"""
    return list(set(a).intersection(b))


def _remove_repeats_from_list(l):
    """去除话题中的重复元素"""
    return list(set(l))
