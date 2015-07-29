# coding: utf-8
import json
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from ._base import db
from ._helpers import pinyin, save_object_to_es, delete_object_from_es, search_objects_from_es


class User(db.Model):
    """用户"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True)
    name_pinyin = db.Column(db.String(200))
    name_edit_count = db.Column(db.Integer, default=2)  # 剩余的称呼修改次数
    email = db.Column(db.String(100), unique=True)
    inactive_email = db.Column(db.String(100))
    desc = db.Column(db.String(200), )
    avatar = db.Column(db.String(200), default='default_user_avatar.png')
    background = db.Column(db.String(200))
    password = db.Column(db.String(200))
    url_token = db.Column(db.String(100))
    location = db.Column(db.String(100))
    organization = db.Column(db.String(100))
    position = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)

    last_read_compose_feeds_at = db.Column(db.DateTime, default=datetime.now)  # 最后浏览撰写 FEED 的时间
    last_read_notifications_at = db.Column(db.DateTime, default=datetime.now)  # 最后浏览通知的时间
    last_read_message_notifications_at = db.Column(db.DateTime, default=datetime.now)  # 最后浏览消息类通知的时间
    last_read_user_notifications_at = db.Column(db.DateTime, default=datetime.now)  # 最后浏览用户类消息的时间
    last_read_thanks_notifications_at = db.Column(db.DateTime, default=datetime.now)  # 最后浏览感谢类消息的时间

    is_active = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    has_selected_expert_topics = db.Column(db.Boolean, default=False)  # 是否选择了擅长话题
    has_selected_interesting_topics = db.Column(db.Boolean, default=False)  # 是否选择了感兴趣的话题

    # 引导
    has_finish_guide_steps = db.Column(db.Boolean, default=False)  # 是否完成引导步骤
    current_guide_step = db.Column(db.Integer, default=1)  # 当前处于的引导步骤

    # 计数
    followers_count = db.Column(db.Integer, default=0)
    followings_count = db.Column(db.Integer, default=0)
    thanks_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    upvotes_count = db.Column(db.Integer, default=0)
    questions_count = db.Column(db.Integer, default=0)
    answers_count = db.Column(db.Integer, default=0)
    drafts_count = db.Column(db.Integer, default=0)

    # 设置

    # 邀请我回答
    invite_message_from_all = db.Column(db.Boolean, default=True)
    invite_message_via_notification = db.Column(db.Boolean, default=True)
    invite_message_via_mail = db.Column(db.Boolean, default=True)

    # 赞同/感谢了我的回答
    upvote_answer_message_from_all = db.Column(db.Boolean, default=True)
    upvote_answer_message_via_notification = db.Column(db.Boolean, default=True)
    upvote_answer_message_via_mail = db.Column(db.Boolean, default=True)

    # 赞了我的评论
    like_comment_message_from_all = db.Column(db.Boolean, default=True)
    like_comment_message_via_notification = db.Column(db.Boolean, default=True)
    like_comment_message_via_mail = db.Column(db.Boolean, default=True)

    # 关注了我
    follow_message_from_all = db.Column(db.Boolean, default=True)
    follow_message_via_notification = db.Column(db.Boolean, default=True)
    follow_message_via_mail = db.Column(db.Boolean, default=True)

    # 评论了我
    reply_comment_message_from_all = db.Column(db.Boolean, default=True)
    reply_comment_message_via_notification = db.Column(db.Boolean, default=True)
    reply_comment_message_via_mail = db.Column(db.Boolean, default=True)

    # 回答了关注的问题
    answer_question_message_from_all = db.Column(db.Boolean, default=True)
    answer_question_message_via_notification = db.Column(db.Boolean, default=True)
    answer_question_message_via_mail = db.Column(db.Boolean, default=True)

    # 每周精选
    receive_weekly_digest_message = db.Column(db.Boolean, default=True)

    # 不定期的新品/活动通知
    receive_activity_message = db.Column(db.Boolean, default=True)

    # 被搜索引擎搜索到时显示我的姓名
    show_to_search_engine = db.Column(db.Boolean, default=True)

    def __setattr__(self, name, value):
        # Hash password when set it.
        if name == 'password':
            value = generate_password_hash(value)
        elif name == 'name':
            # 为name赋值时，自动设置其拼音
            super(User, self).__setattr__('name_pinyin', pinyin(value))
        super(User, self).__setattr__(name, value)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def followed_by_user(self, user_id):
        """该用户是否被当前用户关注"""
        return FollowUser.query.filter(FollowUser.follower_id == user_id,
                                       FollowUser.following_id == self.id).count() > 0

    def blocked_by_user(self, user_id):
        """该用户是否被当前用户屏蔽"""
        return BlockUser.query.filter(BlockUser.blocked_user_id == self.id,
                                      BlockUser.user_id == user_id).count() > 0

    @property
    def profile_url(self):
        """用户个人主页url"""
        if self.url_token:
            return '%s/people/%s' % (db.config.get('DC_DOMAIN'), self.url_token)
        else:
            return '%s/people/%d' % (db.config.get('DC_DOMAIN'), self.id)

    @property
    def qa_url(self):
        """用户问答url"""
        if self.url_token:
            return '%s/people/%s/qa' % (db.config.get('DC_DOMAIN'), self.url_token)
        else:
            return '%s/people/%d/qa' % (db.config.get('DC_DOMAIN'), self.id)

    @property
    def achievements_url(self):
        """用户成就url"""
        if self.url_token:
            return '%s/people/%s/achievements' % (db.config.get('DC_DOMAIN'), self.url_token)
        else:
            return '%s/people/%d/achievements' % (db.config.get('DC_DOMAIN'), self.id)

    @property
    def avatar_url(self):
        """用户头像"""
        return "%s/%s?imageView2/1/w/240" % (db.config.get('CDN_HOST'), self.avatar)

    @property
    def background_url(self):
        """背景图片"""
        return "%s/%s" % (db.config.get('CDN_HOST'), self.background) if self.background else None

    @property
    def random_answers(self, count=3):
        """随机回答"""
        from .answer import Answer

        return self.answers.filter(~Answer.hide).order_by(db.func.random()).limit(count)

    @property
    def expert_topics(self):
        """用户擅长话题

        当该用户未选择擅长话题时，返回score最高的话题；
        当已选择时，返回选择的擅长话题。
        """
        from .topic import UserTopicStatistic

        if self.has_selected_expert_topics:
            return UserTopicStatistic.query. \
                filter(UserTopicStatistic.user_id == self.id,
                       UserTopicStatistic.selected). \
                order_by(UserTopicStatistic.show_order.asc()).limit(8)
        else:
            return UserTopicStatistic.query. \
                filter(UserTopicStatistic.user_id == self.id). \
                filter(db.or_(UserTopicStatistic.score != 0, UserTopicStatistic.worked_on)). \
                order_by(UserTopicStatistic.worked_on.desc()).order_by(UserTopicStatistic.score.asc()). \
                limit(7)

    def answered_topics(self, count=3):
        """该用户回答过的话题"""
        from .topic import UserTopicStatistic

        return UserTopicStatistic.query.filter(UserTopicStatistic.user_id == self.id,
                                               UserTopicStatistic.score != 0). \
            order_by(UserTopicStatistic.score.desc()).limit(count)

    def save_to_es(self):
        """保存此用户到elasticsearch"""
        return save_object_to_es('user', self.id, {
            'name': self.name,
            'name_pinyin': self.name_pinyin,
            'desc': self.desc,
            'created_at': self.created_at
        })

    def delete_from_es(self):
        """从elasticsearch中删除此用户"""
        return delete_object_from_es('user', self.id)

    @staticmethod
    def query_from_es(q, page=1, per_page=10):
        """在elasticsearch中查询用户"""
        results = search_objects_from_es(doc_type='user', body={
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["name", "name_pinyin", "desc"]
                }
            },
            "highlight": {
                "fields": {
                    "name": {},
                    "desc": {}
                }
            },
            "from": per_page * (page - 1),
            "size": per_page
        })

        result_users = []

        for result in results["hits"]["hits"]:
            id = result["_id"]
            user = User.query.get(id)
            if "highlight" in result:
                if "name" in result["highlight"]:
                    user.highlight_name = result["highlight"]["name"][0]
                if "desc" in result["highlight"]:
                    user.highlight_desc = result["highlight"]["desc"][0]
            result_users.append(user)

        return result_users, results["hits"]["total"], results['took']

    def __repr__(self):
        return '<User %s>' % self.name


class FollowUser(db.Model):
    """关注用户"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    follower = db.relationship('User', backref=db.backref('followings',
                                                          lazy='dynamic',
                                                          order_by='desc(FollowUser.created_at)'),
                               foreign_keys=[follower_id])

    following_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    following = db.relationship('User', backref=db.backref('followers',
                                                           lazy='dynamic',
                                                           order_by='desc(FollowUser.created_at)'),
                                foreign_keys=[following_id])

    def __repr__(self):
        return '<FollowUser %s>' % self.id


class USER_FEED_KIND(object):
    """用户feed类型

    当出现重复行为时（3-6条），仅更新创建时间。
    """
    ASK_QUESTION = "gN02m2F"  # 提问
    ANSWER_QUESTION = "J8AbTDT"  # 回答问题
    UPVOTE_ANSWER = "F9FqDKa"  # 赞同回答
    FOLLOW_QUESTION = "4MYN2Ui"  # 关注问题
    FOLLOW_TOPIC = "wa3PMng"  # 关注话题
    FOLLOW_USER = "vTw5er5"  # 关注人


class UserFeed(db.Model):
    """用户feed"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User',
                           backref=db.backref('feeds',
                                              lazy='dynamic',
                                              order_by='desc(UserFeed.created_at)'),
                           foreign_keys=[user_id])

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic')

    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    question = db.relationship('Question')

    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id'))
    answer = db.relationship('Answer')

    following_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    following = db.relationship('User', foreign_keys=[following_id])

    @staticmethod
    def follow_topic(user, topic):
        """关注话题feed"""
        user_feed = user.feeds.filter(UserFeed.kind == USER_FEED_KIND.FOLLOW_TOPIC,
                                      UserFeed.topic_id == topic.id).first()
        if user_feed:
            user_feed.created_at = datetime.now()
        else:
            user_feed = UserFeed(kind=USER_FEED_KIND.FOLLOW_TOPIC, user_id=user.id, topic_id=topic.id)
        db.session.add(user_feed)

    @staticmethod
    def follow_user(follower, following):
        """关注用户feed"""
        user_feed = follower.feeds.filter(UserFeed.kind == USER_FEED_KIND.FOLLOW_USER,
                                          UserFeed.following_id == following.id).first()
        if user_feed:
            user_feed.created_at = datetime.now()
        else:
            user_feed = UserFeed(kind=USER_FEED_KIND.FOLLOW_USER, user_id=follower.id, following_id=following.id)
        db.session.add(user_feed)

    @staticmethod
    def follow_question(user, question):
        """关注问题feed"""
        user_feed = user.feeds.filter(UserFeed.kind == USER_FEED_KIND.FOLLOW_QUESTION,
                                      UserFeed.question_id == question.id).first()
        if user_feed:
            user_feed.created_at = datetime.now()
        else:
            user_feed = UserFeed(kind=USER_FEED_KIND.FOLLOW_QUESTION, user_id=user.id, question_id=question.id)
        db.session.add(user_feed)

    @staticmethod
    def upvote_answer(user, answer):
        """赞同回答feed"""
        user_feed = user.feeds.filter(UserFeed.kind == USER_FEED_KIND.UPVOTE_ANSWER,
                                      UserFeed.answer_id == answer.id).first()
        if user_feed:
            user_feed.created_at = datetime.now()
        else:
            user_feed = UserFeed(kind=USER_FEED_KIND.UPVOTE_ANSWER, user_id=user.id, answer_id=answer.id)
        db.session.add(user_feed)

    @staticmethod
    def ask_question(user, question):
        """提问feed"""
        user_feed = user.feeds.filter(UserFeed.kind == USER_FEED_KIND.ASK_QUESTION,
                                      UserFeed.question_id == question.id).first()
        if not user_feed:
            user_feed = UserFeed(kind=USER_FEED_KIND.ASK_QUESTION, user_id=user.id, question_id=question.id)
        db.session.add(user_feed)

    @staticmethod
    def answer_question(user, answer):
        """回答feed"""
        user_feed = user.feeds.filter(UserFeed.kind == USER_FEED_KIND.ANSWER_QUESTION,
                                      UserFeed.answer_id == answer.id).first()
        if not user_feed:
            user_feed = UserFeed(kind=USER_FEED_KIND.ANSWER_QUESTION, user_id=user.id, answer_id=answer.id)
        db.session.add(user_feed)


class NOTIFICATION_KIND(object):
    """用户通知子类型"""
    # 用户类通知
    FOLLOW_ME = "nK8BQ99"  # 关注了我

    # 感谢类通知
    UPVOTE_ANSWER = "Vu69o4V"  # 赞同了我的回答
    THANK_ANSWER = "gIWr7dg"  # 感谢了我的回答
    LIKE_ANSWER_COMMENT = "1oY78lq"  # 赞了我的评论

    # 消息类通知
    ANSWER_FROM_ASKED_QUESTION = "WFHhwmW"  # 回答了我提出的问题
    COMMENT_ANSWER = "Fk3cIIH"  # 评论了我的回答
    REPLY_ANSWER_COMMENT = "ibWxLaC"  # 回复了我的评论
    GOOD_ANSWER_FROM_FOLLOWED_TOPIC = "FAKeWIP"  # 关注的问题有了精彩的回答（后台）
    SYSTEM_NOTI = "ezjwiCu"  # 系统通知（后台）
    HIDE_ANSWER = "E0CzTCk"  # 回答被折叠（后台）


class NOTIFICATION_KIND_TYPE(object):
    """用户通知主类型"""
    # 消息类
    MESSAGE = [NOTIFICATION_KIND.ANSWER_FROM_ASKED_QUESTION,
               NOTIFICATION_KIND.COMMENT_ANSWER,
               NOTIFICATION_KIND.REPLY_ANSWER_COMMENT,
               NOTIFICATION_KIND.GOOD_ANSWER_FROM_FOLLOWED_TOPIC,
               NOTIFICATION_KIND.SYSTEM_NOTI,
               NOTIFICATION_KIND.HIDE_ANSWER]

    USER = [NOTIFICATION_KIND.FOLLOW_ME]

    THANKS = [NOTIFICATION_KIND.UPVOTE_ANSWER,
              NOTIFICATION_KIND.THANK_ANSWER,
              NOTIFICATION_KIND.LIKE_ANSWER_COMMENT]


class Notification(db.Model):
    """用户消息"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_at_date = db.Column(db.Date, default=date.today())
    unread = db.Column(db.Boolean, default=True)

    # 消息接收者
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User',
                           backref=db.backref('notifications',
                                              lazy='dynamic',
                                              order_by='desc(Notification.created_at)'),
                           foreign_keys=[user_id])

    # 消息发起者，为用户 id 的列表
    senders_list = db.Column(db.Text)
    merged = db.Column(db.Boolean, default=False)  # 是否为合并过的消息

    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender = db.relationship('User', foreign_keys=[sender_id])

    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    question = db.relationship('Question')

    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id'))
    answer = db.relationship('Answer')

    answer_comment_id = db.Column(db.Integer, db.ForeignKey('answer_comment.id'))
    answer_comment = db.relationship('AnswerComment')

    def last_in_that_day(self, user_id):
        """该问题是否为当天最晚的消息"""
        day = self.created_at.date()
        noti = Notification.query. \
            filter(db.func.date(Notification.created_at) == day,
                   Notification.user_id == user_id). \
            order_by(Notification.created_at.desc()).first()
        return noti is not None and noti.id == self.id

    def add_sender(self, sender_id):
        """添加发起者"""
        senders_list = set(json.loads(self.senders_list or "[]"))
        senders_list.add(sender_id)
        self.senders_list = json.dumps(list(senders_list))

    @property
    def senders(self):
        """该消息的全部发起者"""
        if not self.senders_list:
            return None
        senders_id_list = json.loads(self.senders_list)
        return User.query.filter(User.id.in_(senders_id_list))

    @staticmethod
    def follow_me(follower, following):
        """关注了我NOTI"""
        noti = following.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.FOLLOW_ME,
            Notification.sender_id == follower.id).first()
        if not noti:
            noti = Notification(kind=NOTIFICATION_KIND.FOLLOW_ME, sender_id=follower.id)
            following.notifications.append(noti)
            db.session.add(following)

    @staticmethod
    def upvote_answer(user, answer):
        """赞同回答NOTI"""
        noti = answer.user.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.UPVOTE_ANSWER,
            Notification.sender_id == user.id,
            ~Notification.merged,
            Notification.answer_id == answer.id).first()
        if noti:
            return
        noti = Notification(kind=NOTIFICATION_KIND.UPVOTE_ANSWER, sender_id=user.id, answer_id=answer.id,
                            user_id=answer.user.id, unread=False)
        db.session.add(noti)

        # 合并NOTI
        merged_noti = answer.user.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.UPVOTE_ANSWER,
            Notification.unread,
            Notification.merged,
            Notification.answer_id == answer.id,
            Notification.created_at_date == date.today()).first()
        if merged_noti:
            merged_noti.add_sender(user.id)
            db.session.add(merged_noti)
        else:
            merged_noti = Notification(kind=NOTIFICATION_KIND.UPVOTE_ANSWER, senders_list=json.dumps([user.id]),
                                       answer_id=answer.id, merged=True, user_id=answer.user.id)
            db.session.add(merged_noti)

    @staticmethod
    def thank_answer(user, answer):
        """感谢回答NOTI"""
        noti = answer.user.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.THANK_ANSWER,
            Notification.sender_id == user.id,
            ~Notification.merged,
            Notification.answer_id == answer.id).first()
        if noti:
            return
        noti = Notification(kind=NOTIFICATION_KIND.THANK_ANSWER, sender_id=user.id, answer_id=answer.id,
                            user_id=answer.user.id, unread=False)
        db.session.add(noti)

        # 合并NOTI
        merged_noti = answer.user.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.THANK_ANSWER,
            Notification.unread,
            Notification.merged,
            Notification.answer_id == answer.id,
            Notification.created_at_date == date.today()).first()
        if merged_noti:
            merged_noti.add_sender(user.id)
            db.session.add(merged_noti)
        else:
            merged_noti = Notification(kind=NOTIFICATION_KIND.THANK_ANSWER, senders_list=json.dumps([user.id]),
                                       answer_id=answer.id, merged=True, user_id=answer.user.id)
            db.session.add(merged_noti)

    @staticmethod
    def like_answer_comment(user, answer_comment):
        """赞回答评论NOTI"""
        noti = answer_comment.user.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.LIKE_ANSWER_COMMENT,
            Notification.sender_id == user.id,
            ~Notification.merged,
            Notification.answer_comment_id == answer_comment.id).first()
        if noti:
            return
        noti = Notification(kind=NOTIFICATION_KIND.LIKE_ANSWER_COMMENT, sender_id=user.id,
                            answer_comment_id=answer_comment.id, user_id=answer_comment.user.id, unread=False)
        db.session.add(noti)

        # 合并NOTI
        merged_noti = answer_comment.user.notifications.filter(
            Notification.kind == NOTIFICATION_KIND.LIKE_ANSWER_COMMENT,
            Notification.unread,
            Notification.merged,
            Notification.answer_comment_id == answer_comment.id,
            Notification.created_at_date == date.today()).first()
        if merged_noti:
            merged_noti.add_sender(user.id)
            db.session.add(merged_noti)
        else:
            merged_noti = Notification(kind=NOTIFICATION_KIND.LIKE_ANSWER_COMMENT, senders_list=json.dumps([user.id]),
                                       answer_comment_id=answer_comment.id, merged=True, user_id=answer_comment.user.id)
            db.session.add(merged_noti)

    @staticmethod
    def answer_from_asked_question(user, answer):
        """回答问题NOTI"""
        noti = Notification(kind=NOTIFICATION_KIND.ANSWER_FROM_ASKED_QUESTION, sender_id=user.id,
                            answer_id=answer.id, user_id=answer.question.user_id)
        db.session.add(noti)

    @staticmethod
    def comment_answer(user, answer_comment):
        """评论回答NOTI"""
        noti = Notification(kind=NOTIFICATION_KIND.COMMENT_ANSWER, sender_id=user.id,
                            answer_comment_id=answer_comment.id, user_id=answer_comment.answer.user_id)
        db.session.add(noti)

    @staticmethod
    def reply_answer_comment(user, answer_comment):
        """回复评论NOTI"""
        noti = Notification(kind=NOTIFICATION_KIND.REPLY_ANSWER_COMMENT, sender_id=user.id,
                            answer_comment_id=answer_comment.id, user_id=answer_comment.parent.user_id)
        db.session.add(noti)


class HOME_FEED_KIND(object):
    """首页feed类型"""
    FOLLOWING_UPVOTE_ANSWER = "UdW38Gw"  # 我关注的人赞同某个回答
    FOLLOWING_ASK_QUESTION = "groYn17"  # 我关注的人提出了某个问题
    FOLLOWING_ANSWER_QUESTION = "wFyvyTI"  # 我关注的人回答了某个问题
    FOLLOWING_FOLLOW_QUESTION = "i1VEDr8"  # 我关注的人关注了某个问题
    FANTASTIC_ANSWER_FROM_FOLLOWED_TOPIC = "HVKEV0N"  # 关注的话题下的精彩回答


class HomeFeed(db.Model):
    """登录用户的首页feed"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User',
                           backref=db.backref('home_feeds',
                                              lazy='dynamic',
                                              order_by='desc(HomeFeed.created_at)'),
                           foreign_keys=[user_id])

    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender = db.relationship('User', foreign_keys=[sender_id])

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic')

    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    question = db.relationship('Question')

    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id'))
    answer = db.relationship('Answer')

    @staticmethod
    def following_upvote_answer(user, sender, answer):
        """关注的人赞同回答feed"""
        home_feed = user.home_feeds.filter(HomeFeed.kind == HOME_FEED_KIND.FOLLOWING_UPVOTE_ANSWER,
                                           HomeFeed.sender_id == sender.id,
                                           HomeFeed.answer_id == answer.id).first()
        if not home_feed:
            home_feed = HomeFeed(kind=HOME_FEED_KIND.FOLLOWING_UPVOTE_ANSWER,
                                 user_id=user.id, sender_id=sender.id, answer_id=answer.id)
            db.session.add(home_feed)

    @staticmethod
    def following_ask_question(user, sender, question):
        """关注的人提出了问题feed"""
        home_feed = user.home_feeds.filter(HomeFeed.kind == HOME_FEED_KIND.FOLLOWING_ASK_QUESTION,
                                           HomeFeed.sender_id == sender.id,
                                           HomeFeed.question_id == question.id).first()
        if not home_feed:
            home_feed = HomeFeed(kind=HOME_FEED_KIND.FOLLOWING_ASK_QUESTION,
                                 user_id=user.id, sender_id=sender.id, question_id=question.id)
            db.session.add(home_feed)

    @staticmethod
    def following_answer_question(user, sender, answer):
        """关注的人回答问题feed"""
        home_feed = user.home_feeds.filter(HomeFeed.kind == HOME_FEED_KIND.FOLLOWING_ANSWER_QUESTION,
                                           HomeFeed.sender_id == sender.id,
                                           HomeFeed.answer_id == answer.id).first()
        if not home_feed:
            home_feed = HomeFeed(kind=HOME_FEED_KIND.FOLLOWING_ANSWER_QUESTION,
                                 user_id=user.id, sender_id=sender.id, answer_id=answer.id)
            db.session.add(home_feed)

    @staticmethod
    def following_follow_question(user, sender, question):
        """关注的人关注了问题feed"""
        home_feed = user.home_feeds.filter(HomeFeed.kind == HOME_FEED_KIND.FOLLOWING_FOLLOW_QUESTION,
                                           HomeFeed.sender_id == sender.id,
                                           HomeFeed.question_id == question.id).first()
        if not home_feed:
            home_feed = HomeFeed(kind=HOME_FEED_KIND.FOLLOWING_FOLLOW_QUESTION,
                                 user_id=user.id, sender_id=sender.id, question_id=question.id)
            db.session.add(home_feed)


class HomeFeedBackup(db.Model):
    """首页 FEED 备份，用于当新用户注册并关注用户后，为其首页 FEED 填充内容"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender = db.relationship('User', foreign_keys=[sender_id])

    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic')

    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    question = db.relationship('Question')

    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id'))
    answer = db.relationship('Answer')


class COMPOSE_FEED_KIND(object):
    """撰写feed类型"""
    INVITE_TO_ANSWER = "kdcKRfi"  # 别人邀请我回答的问题
    WAITING_FOR_ANSWER_QUESTION_FROM_EXPERT_TOPIC = "v0KJCX3"  # 我擅长的话题下的待回答问题
    WAITING_FOR_ANSWER_QUESTION_FROM_ALL = "4Q8wfm9"  # 全站热门的待回答问题（偶尔）
    WAITING_FOR_ANSWER_QUESTION_FROM_ANSWERED_TOPIC = "JlPzjXf"  # 我没有写进擅长话题，但我之前有过回答的话题下的热门待回答问题


class ComposeFeed(db.Model):
    """撰写feed"""
    __bind_key__ = 'dc'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50))
    ignore = db.Column(db.Boolean, default=False)  # 忽略
    answered = db.Column(db.Boolean, default=False)
    unread = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User',
                           backref=db.backref('compose_feeds',
                                              lazy='dynamic',
                                              order_by='desc(ComposeFeed.created_at)'))

    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    question = db.relationship('Question')

    invitation_id = db.Column(db.Integer, db.ForeignKey('invite_answer.id'))
    invitation = db.relationship('InviteAnswer')

    @staticmethod
    def invite_to_answer(user, question, invitation):
        """邀请回答feed"""
        compose_feed = user.compose_feeds.filter(ComposeFeed.kind == COMPOSE_FEED_KIND.INVITE_TO_ANSWER,
                                                 ComposeFeed.question_id == question.id,
                                                 ComposeFeed.invitation_id == invitation.id).first()
        if not compose_feed:
            compose_feed = ComposeFeed(kind=COMPOSE_FEED_KIND.INVITE_TO_ANSWER, user_id=user.id,
                                       question_id=question.id, invitation_id=invitation.id)
            db.session.add(compose_feed)

    @staticmethod
    def waiting_for_answer_question_from_expert_topic(user, question):
        """擅长话题下的待回答问题feed"""
        compose_feed = user.compose_feeds.filter(ComposeFeed.question_id == question.id).first()
        if not compose_feed:
            compose_feed = ComposeFeed(kind=COMPOSE_FEED_KIND.WAITING_FOR_ANSWER_QUESTION_FROM_EXPERT_TOPIC,
                                       user_id=user.id, question_id=question.id)
            db.session.add(compose_feed)

    @staticmethod
    def waiting_for_answer_question_from_all(user, question):
        """全站热门的待回答问题feed"""
        compose_feed = user.compose_feeds.filter(ComposeFeed.question_id == question.id).first()
        if not compose_feed:
            compose_feed = ComposeFeed(kind=COMPOSE_FEED_KIND.WAITING_FOR_ANSWER_QUESTION_FROM_ALL,
                                       user_id=user.id, question_id=question.id)
            db.session.add(compose_feed)

    @staticmethod
    def waiting_for_answer_question_from_answered_topic(user, question):
        """我没有写进擅长话题，但我之前有过回答的话题下的热门待回答问题feed"""
        compose_feed = user.compose_feeds.filter(ComposeFeed.question_id == question.id).first()
        if not compose_feed:
            compose_feed = ComposeFeed(kind=COMPOSE_FEED_KIND.WAITING_FOR_ANSWER_QUESTION_FROM_ANSWERED_TOPIC,
                                       user_id=user.id, question_id=question.id)
            db.session.add(compose_feed)
