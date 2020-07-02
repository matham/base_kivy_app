"""Configuration
==================

"""

from functools import partial
from tree_config import Configurable, read_config_from_object, apply_config, \
    read_config_from_file, load_config as \
    orig_load_config, dump_config as orig_dump_config, \
    load_apply_save_config as orig_load_apply_save_config
from tree_config.doc_gen import \
    create_doc_listener as orig_create_doc_listener, write_config_props_rst
from base_kivy_app.utils import yaml_dumps

__all__ = (
    'Configurable', 'read_config_from_object', 'apply_config',
    'read_config_from_file', 'load_config', 'dump_config',
    'load_apply_save_config', 'create_doc_listener', 'write_config_props_rst')


load_config = partial(orig_load_config, yaml_dump_str=yaml_dumps)
dump_config = partial(orig_dump_config, yaml_dump_str=yaml_dumps)
load_apply_save_config = partial(
    orig_load_apply_save_config, yaml_dump_str=yaml_dumps)
create_doc_listener = partial(
    orig_create_doc_listener, yaml_dump_str=yaml_dumps)
