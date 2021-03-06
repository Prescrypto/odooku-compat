import click
import tempfile
import sys
import os
from contextlib import closing

from odooku.cli.helpers import resolve_db_name


__all__ = [
    'database'
]


CHUNK_SIZE = 16 * 1024


@click.command()
@click.option(
    '--db-name',
    callback=resolve_db_name
)
@click.option(
    '--module',
    multiple=True
)
@click.option(
    '--demo-data',
    is_flag=True,
)
@click.pass_context
def preload(ctx, db_name, module, demo_data):
    config = (
        ctx.obj['config']
    )

    from odoo.modules.registry import RegistryManager

    if module:
        modules = {
            module_name: 1
            for module_name in module
        }
        config['init'] = dict(modules)

    registry = RegistryManager.new(db_name, force_demo=demo_data, update_module=True)


@click.command()
@click.option(
    '--db-name',
    callback=resolve_db_name
)
@click.option(
    '--module',
    multiple=True
)
@click.pass_context
def update(ctx, db_name, module):
    config = (
        ctx.obj['config']
    )

    from odoo.modules.registry import RegistryManager

    module = module or ['all']
    modules = {
        module_name: 1
        for module_name in module
    }

    config['update'] = dict(modules)
    registry = RegistryManager.new(db_name, update_module=True)


@click.command()
@click.option(
    '--db-name',
    callback=resolve_db_name
)
@click.pass_context
def newdbuuid(ctx, db_name):
    config = (
        ctx.obj['config']
    )

    from odoo.modules.registry import RegistryManager

    registry = RegistryManager.get(db_name)
    with Environment.manage():
        with registry.cursor() as cr:
            registry['ir.config_parameter'].init(cr, force=True)


@click.command()
@click.option(
    '--db-name',
    callback=resolve_db_name
)
@click.option(
    '--s3-file'
)
@click.pass_context
def dump(ctx, db_name, s3_file):
    config = (
        ctx.obj['config']
    )

    from odooku.s3 import pool as s3_pool
    from odoo.api import Environment
    from odoo.service.db import dump_db

    with tempfile.TemporaryFile() as t:
        with Environment.manage():
            dump_db(db_name, t)

        t.seek(0)
        if s3_file:
            s3_pool.client.upload_fileobj(t, s3_pool.bucket, s3_file)
        else:
            # Pipe to stdout
            while True:
                chunk = t.read(CHUNK_SIZE)
                if not chunk:
                    break
                sys.stdout.write(chunk)


@click.command()
@click.option(
    '--db-name',
    callback=resolve_db_name
)
@click.option(
    '--copy',
    is_flag=True
)
@click.option(
    '--s3-file'
)
@click.pass_context
def restore(ctx, db_name, copy, s3_file):
    config = (
        ctx.obj['config']
    )

    if update:
        config['update']['all'] = 1

    from odooku.s3 import pool as s3_pool
    from odoo.api import Environment
    from odoo.service.db import restore_db

    with tempfile.NamedTemporaryFile(delete=False) as t:
        if s3_file:
            s3_pool.client.download_fileobj(s3_pool.bucket, s3_file, t)
        else:
            # Read from stdin
            while True:
                chunk = sys.stdin.read(CHUNK_SIZE)
                if not chunk:
                    break
                t.write(chunk)
        t.close()

        with Environment.manage():
            restore_db(
                db_name,
                t.name,
                copy=copy
            )

        os.unlink(t.name)


@click.group()
@click.pass_context
def database(ctx):
    pass


database.add_command(preload)
database.add_command(update)
database.add_command(newdbuuid)
database.add_command(dump)
database.add_command(restore)
