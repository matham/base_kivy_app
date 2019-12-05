"""Config
==========

Configuration used across kivy apps.

Overview
---------

Configuration works as follows. Each class that has configuration attributes
must list these attributes in a list in the class ``__config_props__``
attribute. Each of the properties listed there must be "Kivy" properties of
that class.

When generating docs, the documentation of these properties are dumped to
a json file using :func:`create_doc_listener`.

Each app instance defines a application class based on
:class:`~base_kivy_app.app.BaseKivyApp`. Using this classe's
:meth:`~base_kivy_app.app.BaseKivyApp.get_config_classes` method we get a list
of all classes used in the current app that requires configuration
and :func:`write_config_attrs_rst` is used to combine all these docs
and display them in a single place in the generated html pages.

Similarly, when the app is run, a single json file is generated with all these
config values and is later read and is used to configure the app by the
user. :attr:`~base_kivy_app.app.BaseKivyApp.app_settings` is where it's stored
after reading. Each class is responsible for reading its configuration
from there.

Usage
-----

When creating an app, ensure that the app
inherited from :class:`~base_kivy_app.app.BaseKivyApp` overwrites the
:meth:`~base_kivy_app.app.BaseKivyApp.get_config_classes` method
returning all the classes that need configuration.

Then, in the sphinx conf.py file do::

    def setup(app):
        import package
        from package import MyApp
        fname = os.environ.get(
            'BASEKIVYAPP_CONFIG_DOC_PATH', 'config_attrs.json')
        create_doc_listener(app, package, fname)
        if MyApp.get_running_app() is not None:
            classes = MyApp.get_running_app().get_config_instances()
        else:
            classes = MyApp.get_config_classes()

        app.connect(
            'build-finished', partial(
                write_config_attrs_rst, classes, package, filename=fname)
        )

and run `make html` twice. This will create the ``config_attrs.json`` file
and the config.rst file under source/. This
config.rst should have been listed in the sphinx index so on the second run
this file will be converted to html containing all the config tokens.

You should similarly run doc generation for all packages the your package
relies on so you get all their config options in ``config_attrs.json``
so they can be included in the docs.
"""

import operator
from inspect import isclass
from os.path import join
import re
from importlib import import_module
import json
from collections import deque
from kivy.properties import Property
from base_kivy_app.utils import yaml_loads, yaml_dumps

__all__ = ('read_config_from_object', 'read_config_from_file', 'apply_config',
           'dump_config', 'create_doc_listener',
           'get_config_attrs_doc', 'write_config_attrs_rst')

config_list_pat = re.compile(
    '\\[\\s+([^",\\]\\s{}]+,\\s+)*[^",\\]\\s{}]+\\s+\\]')
config_whitesp_pat = re.compile('\\s')


def _get_bases(cls):
    for base in cls.__bases__:
        if base.__name__ == 'object':
            break
        for cbase in _get_bases(base):
            yield cbase
        yield base


def _get_settings_attrs(cls):
    """Returns a list of configurable properties of the class.

    :param cls:
    :return:
    """
    attrs = []
    for c in [cls] + list(_get_bases(cls)):
        if '__config_props__' not in c.__dict__:
            continue

        for attr in c.__config_props__:
            if attr in attrs:
                continue
            if not hasattr(cls, attr):
                raise Exception('Missing attribute <{}> in <{}>'.
                                format(attr, cls.__name__))
            attrs.append(attr)
    return attrs


def _get_classes_settings_attrs(cls):
    """Returns a dictionary of parent classes that maps class names to a dict
    of properties and their info.

    :param cls:
    :return:
    """
    attrs = {}
    for c in [cls] + list(_get_bases(cls)):
        if '__config_props__' not in c.__dict__ or not c.__config_props__:
            continue

        for attr in c.__config_props__:
            if not hasattr(cls, attr):
                raise Exception('Missing attribute <{}> in <{}>'.
                                format(attr, cls.__name__))
        attrs['{}.{}'.format(c.__module__, c.__name__)] = {
            attr: [getattr(c, attr).defaultvalue, None]
            for attr in c.__config_props__}
    return attrs


def fill_config_from_declared_objects(root_obj, classes, config):
    for name, obj in classes.items():
        if isinstance(obj, dict):
            config[name] = {
                k: read_config_from_object(o, o is root_obj)
                for k, o in obj.items()}
        elif isinstance(obj, (list, tuple)):
            config[name] = [
                read_config_from_object(o, o is root_obj) for o in obj]
        else:
            config[name] = read_config_from_object(obj, obj is root_obj)


def read_config_from_object(obj, get_props_only=False):
    config = {}

    if not get_props_only:
        objects = None
        # get all the configurable classes used by the obj
        if isclass(obj):
            if hasattr(obj, 'get_config_classes'):
                objects = obj.get_config_classes()
        else:
            if hasattr(obj, 'get_config_instances'):
                objects = obj.get_config_instances()

        if objects is not None:
            fill_config_from_declared_objects(obj, objects, config)
            # have we already processed this objects config props?
            if obj in list(objects.values()):
                return config

    if isclass(obj):
        for attr in _get_settings_attrs(obj):
            prop_val = getattr(obj, attr)
            if isinstance(prop_val, Property):
                config[attr] = prop_val.defaultvalue
            else:
                config[attr] = prop_val
    else:
        props = _get_settings_attrs(obj.__class__)
        if hasattr(obj, 'get_config_properties'):
            config.update(obj.get_config_properties())

        for attr in props:
            if attr not in config:
                config[attr] = getattr(obj, attr)
    return config


def read_config_from_file(filename):
    """Reads the config file and loads all the config data.

    The config data is returned as a dict. If there's an error, an empty dict
    is returned.
    """
    try:
        with open(filename) as fh:
            opts = yaml_loads(fh.read())
        if opts is None:
            opts = {}
        return opts
    except IOError:
        return {}


def apply_config_to_declared_objects(root_obj, classes, config):
    for name, obj in classes.items():
        if name in config:
            if not hasattr(root_obj, 'apply_config_instance') or not \
                    root_obj.apply_config_instance(name, obj, config[name]):
                apply_config(obj, config[name], obj is root_obj)


def apply_config(obj, config, set_props_only=False):
    """Takes the config data read with :func:`read_config_from_object`
    or :func:`read_config_from_file` and applies
    them to any existing class instances listed in classes.
    """
    objects = None
    # get all the configurable classes used by the obj
    if isclass(obj):
        if hasattr(obj, 'get_config_classes'):
            objects = obj.get_config_classes()
    else:
        if hasattr(obj, 'get_config_instances'):
            objects = obj.get_config_instances()

    if not set_props_only and objects is not None:
        apply_config_to_declared_objects(obj, objects, config)
        # have we already processed this objects config props?
        if obj in list(objects.values()):
            return

    if isclass(obj) or not obj:
        return

    used_keys = set() if not objects else set(objects.keys())
    config_values = {k: v for k, v in config.items() if k not in used_keys}

    used_keys = set()
    if hasattr(obj, 'apply_config_properties'):
        used_keys = obj.apply_config_properties(config_values)

    for k, v in config_values.items():
        if k in used_keys:
            continue
        setattr(obj, k, v)


def dump_config(filename, data):
    with open(filename, 'w') as fh:
        fh.write(yaml_dumps(data))


def create_doc_listener(sphinx_app, package, filename='config_attrs.json'):
    """Creates a listener for the ``__config_props__`` attributes and dumps
    the docs of any props listed to ``filename``. If the file
    already exists, it extends it with new data and overwrites any exiting
    properties that we see again in this run.

    To use, in the sphinx conf.py file do::

        def setup(app):
            import package
            create_doc_listener(
                app, package,
                os.environ.get(
                    'BASEKIVYAPP_CONFIG_DOC_PATH', 'config_attrs.json')
            )

    where ``package`` is the module for which the docs are generated.
    """
    try:
        with open(filename) as fh:
            data = json.load(fh)
    except IOError:
        data = {}

    def config_attrs_doc_listener(app, what, name, obj, options, lines):
        if not name.startswith(package.__name__):
            return

        if what == 'class':
            if hasattr(obj, '__config_props__'):
                # get all the baseclasses of this package of this class
                for c, attrs in _get_classes_settings_attrs(obj).items():
                    if not c.startswith(package.__name__):
                        continue

                    # ew haven't seen this class before
                    if name not in data:
                        # just add items for all props
                        data[name] = {n: [] for n in attrs}
                    else:
                        # we have seen this class, add only missing props
                        cls_data = data[name]
                        for n in attrs:
                            if n not in cls_data:
                                cls_data[n] = []
        elif what == 'attribute':
            # now that we saw the class, we fill in the prop docs
            parts = name.split('.')  # parts of the prop path x.Class.prop
            cls = '.'.join(parts[:-1])  # full class path x.Class
            # we have seen the class and prop?
            if cls in data and parts[-1] in data[cls]:
                data[cls][parts[-1]] = lines

    def dump_config_attrs_doc(app, exception):
        # dump config docs
        with open(filename, 'w') as fh:
            json.dump(data, fh, sort_keys=True, indent=4,
                      separators=(',', ': '))

    sphinx_app.connect('autodoc-process-docstring', config_attrs_doc_listener)
    sphinx_app.connect('build-finished', dump_config_attrs_doc)


def walk_config_classes_flat(obj):
    classes_flat = []  # stores all the configurable classes
    stack = deque([(-1, '', obj)])

    while stack:
        level, name, obj = stack.popleft()
        # now we "visited" obj
        classes_flat.append((level, name, obj, {}, {}))

        children = {}
        if isclass(obj):
            if hasattr(obj, 'get_config_classes'):
                children = obj.get_config_classes()
        else:
            if hasattr(obj, 'get_config_instances'):
                children = obj.get_config_instances()

        for child_name, child_obj in sorted(
                children.items(), key=lambda x: x[0]):
            if obj is child_obj:
                continue

            if isinstance(child_obj, dict):
                for k, o in child_obj.items():
                    stack.appendleft((
                        level + 1, '{} --- {}'.format(child_name, k), o))
            elif isinstance(child_obj, (list, tuple)):
                for i, o in enumerate(child_obj):
                    stack.appendleft((
                        level + 1, '{} --- {}'.format(child_name, i), o))
            else:
                stack.appendleft((level + 1, child_name, child_obj))

    assert len(classes_flat) >= 1
    return classes_flat


def get_config_attrs_doc(obj, filename='config_attrs.json'):
    """Objects is a dict of object (class) paths and keys are the names of the
    config attributes of the class.
    """
    classes_flat = walk_config_classes_flat(obj)

    # get the modules associated with each of the classes
    for _, _, obj, classes_props, _ in classes_flat:
        cls = obj if isclass(obj) else obj.__class__
        if not _get_settings_attrs(cls):
            continue

        # get all the parent classes of the class and their props
        classes_props.update(_get_classes_settings_attrs(cls))

    # get the saved docs
    with open(filename) as fh:
        docs = json.load(fh)

    # mapping of class name to a mapping of class props to their docs
    for level, name, obj, classes_props, props_docs in classes_flat:
        for cls, props in classes_props.items():
            cls_docs = docs.get(cls, {})
            for prop in props:
                props[prop][1] = cls_docs.get(prop, [])
                props_docs[prop] = props[prop]
    return classes_flat


def write_config_attrs_rst(
        obj, package, app, exception, filename='config_attrs.json',
        rst_fname=join('source', 'config.rst')):
    """Walks through all the configurable classes of this package
    (should be gotten from
    :meth:`~base_kivy_app.app.BaseKivyApp.get_config_classes` or
    :meth:`~base_kivy_app.app.BaseKivyApp.get_config_instances`) and loads the
    docs of those properties and generates a rst output file with all the
    tokens.

    For example in the sphinx conf.py file do::

        def setup(app):
            app.connect('build-finished', partial(write_config_attrs_rst, \
ProjectApp.get_config_classes(), project_name))

    where project_name is the project module and ProjectApp is the App of the
    package.
    """
    headings = [
        '-', '`', ':', "'", '"', '~', '^', '_', '*', '+', '#', '<', '>']
    n = len(headings) - 1

    # get the docs for the props
    classes_flat = get_config_attrs_doc(obj, filename)

    header = '{} Config'.format(package.__name__.upper())
    lines = [
        header, '=' * len(header), '',
        'The following are the configuration options provided by the app. '
        'It can be configured by changing appropriate values in the '
        '``config.yaml`` file. The options default to the default value '
        'in the classes configurable by these options.', '']

    for level, name, _, _, props_docs in classes_flat:
        if level >= 0:
            lines.append(name)
            lines.append(headings[min(level, n)] * len(name))
            lines.append('')
        for prop, (default, doc) in sorted(
                props_docs.items(), key=operator.itemgetter(0)):
            if isinstance(default, str):
                lines.append('`{}`: "{}"'.format(prop, default))
            else:
                lines.append('`{}`: {}'.format(prop, default))
            while doc and not doc[-1].strip():
                del doc[-1]

            lines.extend([' ' + d for d in doc if d])
            lines.append('')
        lines.append('')

    lines = '\n'.join(lines)
    try:
        with open(rst_fname) as fh:
            if fh.read() == lines:
                return
    except IOError:
        pass

    with open(rst_fname, 'w') as fh:
        fh.write(lines)
