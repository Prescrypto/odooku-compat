import click
import urlparse

from odooku.params import params
from odooku.cli.helpers import prefix_envvar, resolve_addons

import logging


@click.group()
@click.option(
    '--database-url',
    required=True,
    envvar="DATABASE_URL",
    help="[database type]://[username]:[password]@[host]:[port]/[database name]"
)
@click.option(
    '--database-maxconn',
    default=20,
    envvar=prefix_envvar("DATABASE_MAXCONN"),
    type=click.INT,
    help="""
    Maximum number of database connections per worker.
    See Heroku Postgres plans.
    """
)
@click.option(
    '--redis-maxconn',
    default=20,
    envvar=prefix_envvar("REDIS_MAXCONN"),
    type=click.INT,
    help="""
    Maximum number of redis connections per worker.
    See Heroku Redis plans.
    """
)
@click.option(
    '--redis-url',
    envvar="REDIS_URL",
    help="redis://[password]@[host]:[port]/[database number]"
)
@click.option(
    '--aws-access-key-id',
    envvar="AWS_ACCESS_KEY_ID",
    help="Your AWS access key id."
)
@click.option(
    '--aws-secret-access-key',
    envvar="AWS_SECRET_ACCESS_KEY",
    help="Your AWS secret access key."
)
@click.option(
    '--aws-region',
    envvar="AWS_REGION",
    help="Your AWS region."
)
@click.option(
    '--s3-bucket',
    envvar="S3_BUCKET",
    help="S3 bucket for filestore."
)
@click.option(
    '--s3-endpoint-url',
    envvar="S3_ENDPOINT_URL",
    help="S3 endpoint url."
)
@click.option(
    '--s3-custom-domain',
    envvar="S3_CUSTOM_DOMAIN",
    help="S3 custom domain."
)
@click.option(
    '--s3-addressing-style',
    envvar="S3_ADDRESSING_STYLE",
    type=click.Choice(['path', 'virtual']),
    help="S3 addressing style."
)
@click.option(
    '--addons',
    required=True,
    callback=resolve_addons,
    envvar=prefix_envvar('ADDONS')
)
@click.option(
    '--tmp-dir',
    default='/tmp/odooku',
    envvar=prefix_envvar('TMP_DIR')
)
@click.option(
    '--debug',
    is_flag=True,
    envvar=prefix_envvar('DEBUG')
)
@click.option(
    '--statsd-host',
    envvar=prefix_envvar('STATSD_HOST')
)
@click.pass_context
def main(ctx, database_url, database_maxconn, redis_url, redis_maxconn,
        aws_access_key_id, aws_secret_access_key, aws_region, s3_bucket,
        s3_endpoint_url, s3_custom_domain, s3_addressing_style,
        addons, tmp_dir, debug, statsd_host):

    # Setup logger first, then import further modules
    import odooku.logger
    odooku.logger.setup(debug=debug, statsd_host=statsd_host)
    from odooku import redis, s3

    # Setup S3
    s3.configure(
        bucket=s3_bucket,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region=aws_region,
        endpoint_url=s3_endpoint_url,
        custom_domain=s3_custom_domain,
        addressing_style=s3_addressing_style,
    )

    # Setup Redis
    redis_url = urlparse.urlparse(redis_url) if redis_url else None
    redis.configure(
        host=redis_url.hostname if redis_url else None,
        port=redis_url.port if redis_url else None,
        password=redis_url.password if redis_url else None,
        db_number=redis_url.path[1:] if redis_url and redis_url.path else None,
        maxconn=redis_maxconn
    )

    # Setup Odoo
    import odoo
    from odoo.tools import config

    # Always account for multiple processes:
    # - we can run multiple dyno's consisting of:
    #    - web
    #    - worker
    odoo.multi_process = True

    # Patch odoo config
    database_url = urlparse.urlparse(database_url)
    config.parse_config()
    db_name = database_url.path[1:] if database_url.path else False
    config['data_dir'] = tmp_dir
    config['addons_path'] = addons
    config['db_name'] = db_name
    config['db_user'] = database_url.username
    config['db_password'] = database_url.password
    config['db_host'] = database_url.hostname
    config['db_port'] = database_url.port
    config['db_maxconn'] = database_maxconn

    config['demo'] = {}
    config['without_demo'] = 'all'
    config['debug_mode'] = debug
    config['list_db'] = not bool(db_name)

    logger = logging.getLogger(__name__)
    ctx.obj.update({
        'debug': debug,
        'config': config,
        'params': params,
        'logger': logger
    })


from . import commands
for name in dir(commands):
    member = getattr(commands, name)
    if isinstance(member, click.BaseCommand):
        main.add_command(member)


def entrypoint():
    main(obj={})


if __name__ == '__main__':
    main(obj={})
