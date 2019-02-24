from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError,\
                              MastodonNetworkError,\
                              MastodonNotFoundError,\
                              MastodonRatelimitError,\
                              MastodonUnauthorizedError
from model import MastodonApp, Account, OAuthToken, Post, MastodonInstance
from requests import head
from app import db, sentry
from libforget.exceptions import TemporaryError
from functools import lru_cache


def get_or_create_app(instance_url, callback, website):
    instance_url = instance_url
    app = MastodonApp.query.get(instance_url)
    try:
        head('https://{}'.format(instance_url)).raise_for_status()
        proto = 'https'
    except Exception:
        head('http://{}'.format(instance_url)).raise_for_status()
        proto = 'http'

    if not app:
        client_id, client_secret = Mastodon.create_app(
                'forget',
                scopes=('read', 'write'),
                api_base_url='{}://{}'.format(proto, instance_url),
                redirect_uris=callback,
                website=website,
            )
        app = MastodonApp()
        app.instance = instance_url
        app.client_id = client_id
        app.client_secret = client_secret
        app.protocol = proto
    return app


def anonymous_api(app):
    return Mastodon(
            app.client_id,
            client_secret=app.client_secret,
            api_base_url='{}://{}'.format(app.protocol, app.instance),
            )


def login_url(app, callback):
    return anonymous_api(app).auth_request_url(
            redirect_uris=callback,
            scopes=('read', 'write',)
            )


def receive_code(code, app, callback):
    api = anonymous_api(app)
    access_token = api.log_in(
            code=code,
            scopes=('read', 'write'),
            redirect_uri=callback,
            )

    remote_acc = api.account_verify_credentials()
    acc = account_from_api_object(remote_acc, app.instance)
    acc = db.session.merge(acc)
    token = OAuthToken(token=access_token)
    token = db.session.merge(token)
    token.account = acc

    return token


@lru_cache()
def get_api_for_acc(account):
    app = MastodonApp.query.get(account.mastodon_instance)
    for token in account.tokens:
        api = Mastodon(
                app.client_id,
                client_secret=app.client_secret,
                api_base_url='{}://{}'.format(app.protocol, app.instance),
                access_token=token.token,
                ratelimit_method='throw',
            )
        try:
            # api.verify_credentials()
            # doesnt error even if the token is revoked lol
            # https://github.com/tootsuite/mastodon/issues/4637
            # so we have to do this:
            api.timeline()
            return api
        except MastodonUnauthorizedError as e:
            if sentry:
                sentry.captureMessage(
                        'Mastodon auth revoked or incorrect',
                        extra=locals())
            db.session.delete(token)
            db.session.commit()
            continue
        except MastodonAPIError as e:
            raise TemporaryError(e)
        except (MastodonNetworkError,
                MastodonRatelimitError) as e:
            raise TemporaryError(e)


def fetch_acc(acc, cursor=None):
    api = get_api_for_acc(acc)
    if not api:
        print('no access, aborting')
        return None

    try:
        newacc = account_from_api_object(
                api.account_verify_credentials(), acc.mastodon_instance)
        acc = db.session.merge(newacc)

        kwargs = dict(limit=40)
        if cursor:
            kwargs.update(cursor)

        if 'max_id' not in kwargs:
            most_recent_post = (
                    Post.query.with_parent(acc)
                    .order_by(db.desc(Post.created_at)).first())
            if most_recent_post:
                kwargs['since_id'] = most_recent_post.mastodon_id

        statuses = api.account_statuses(acc.mastodon_id, **kwargs)

        if statuses:
            for status in statuses:
                post = post_from_api_object(status, acc.mastodon_instance)
                db.session.merge(post)
                if 'max_id' not in kwargs:
                    kwargs['max_id'] = int(status['id'])
                kwargs['max_id'] = min(int(kwargs['max_id']), int(status['id']))

        else:
            kwargs = None

        db.session.commit()

        return kwargs
    except (MastodonAPIError,
            MastodonNetworkError,
            MastodonRatelimitError) as e:
        raise TemporaryError(e)


def post_from_api_object(obj, instance):
    return Post(
            mastodon_instance=instance,
            mastodon_id=obj['id'],
            favourite=obj['favourited'],
            has_media=('media_attachments' in obj
                       and bool(obj['media_attachments'])),
            created_at=obj['created_at'],
            author_id=account_from_api_object(obj['account'], instance).id,
            direct=obj['visibility'] == 'direct',
            favourites=obj['favourites_count'],
            reblogs=obj['reblogs_count'],
            is_reblog=obj['reblog'] is not None,
        )


def account_from_api_object(obj, instance):
    return Account(
            mastodon_instance=instance,
            mastodon_id=obj['id'],
            screen_name='{}@{}'.format(obj['username'], instance),
            display_name=obj['display_name'],
            avatar_url=obj['avatar'],
            reported_post_count=obj['statuses_count'],
        )


def refresh_posts(posts):
    acc = posts[0].author
    api = get_api_for_acc(acc)
    if not api:
        raise Exception('no access')

    new_posts = list()
    for post in posts:
        try:
            status = api.status(post.mastodon_id)
            new_post = db.session.merge(
                    post_from_api_object(status, post.mastodon_instance))
            new_post.touch()
            new_posts.append(new_post)
        except MastodonNotFoundError:
            db.session.delete(post)
        except (MastodonAPIError,
                MastodonNetworkError,
                MastodonRatelimitError) as e:
            raise TemporaryError(e)

    return new_posts


def delete(post):
    api = get_api_for_acc(post.author)
    try:
        api.status_delete(post.mastodon_id)
        db.session.delete(post)
    except (MastodonAPIError,
            MastodonNetworkError,
            MastodonRatelimitError) as e:
        raise TemporaryError(e)


def suggested_instances(limit=5, min_popularity=5, blacklist=tuple()):
    return tuple((ins.instance for ins in (
            MastodonInstance.query
            .filter(MastodonInstance.popularity > min_popularity)
            .filter(~MastodonInstance.instance.in_(blacklist))
            .order_by(db.desc(MastodonInstance.popularity),
                      MastodonInstance.instance)
            .limit(limit).all())))
