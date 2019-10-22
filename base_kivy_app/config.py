'''Config
==========

Configuration used across kivy apps.

Overview
---------

Configuration works as follows. Each class that has configuration attributes
must list these attributes in a list in the class ``__settings_attrs__``
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
        fname = os.environ.get('BASEKIVYAPP_CONFIG_DOC_PATH', 'config_attrs.json')
        create_doc_listener(app, package, fname)
        if MyApp.get_running_app() is not None:
            classes = MyApp.get_running_app().get_app_config_classes()
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
'''

import operator
from inspect import isclass
from os.path import join, dirname
import re
from importlib import import_module
import json
from kivy.compat import PY2, string_types
from base_kivy_app.utils import yaml_loads, yaml_dumps

__all__ = ('populate_config', 'apply_config', 'dump_config',
           'populate_dump_config', 'create_doc_listener',
           'get_config_attrs_doc', 'write_config_attrs_rst')

config_list_pat = re.compile(
    '\\[\\s+([^",\\]\\s{}]+,\\s+)*[^",\\]\\s{}]+\\s+\\]')
config_whitesp_pat = re.compile('\\s')


def _get_bases(cls):
    for base in cls.__bases__:
        if base.__name__ == 'object':
            break
        yield base
        for cbase in _get_bases(base):
            yield cbase


def _get_settings_attrs(cls):
    """Returns a list of configurable properties of the class.

    :param cls:
    :return:
    """
    attrs = []
    for c in [cls] + list(_get_bases(cls)):
        if '__settings_attrs__' not in c.__dict__:
                continue

        for attr in c.__settings_attrs__:
            if attr in attrs:
                continue
            if not hasattr(cls, attr):
                raise Exception('Missing attribute <{}> in <{}>'.
                                format(attr, cls.__name__))
            attrs.append(attr)
    return attrs


def _get_classses_settings_attrs(cls):
    """Returns a dictionary of parent classes that maps class names to a dict
    of properties and their info.

    :param cls:
    :return:
    """
    attrs = {}
    for c in [cls] + list(_get_bases(cls)):
        if '__settings_attrs__' not in c.__dict__ or not c.__settings_attrs__:
                continue

        for attr in c.__settings_attrs__:
            if not hasattr(cls, attr):
                raise Exception('Missing attribute <{}> in <{}>'.
                                format(attr, cls.__name__))
        attrs['{}.{}'.format(c.__module__, c.__name__)] = {
            attr: [getattr(c, attr).defaultvalue, None]
            for attr in c.__settings_attrs__}
    return attrs


def _get_config_dict(name, cls, opts):
    obj = cls

    opt = opts.get(name, {})
    new_vals = {}
    if isclass(obj):
        for attr in _get_settings_attrs(obj):
            new_vals[attr] = opt.get(
                attr, getattr(obj, attr).defaultvalue)
    else:
        if hasattr(obj, 'get_settings_attrs'):
            for k, v in obj.get_settings_attrs(
                    _get_settings_attrs(obj.__class__)).items():
                new_vals[k] = opt.get(k, v)
        else:
            for attr in _get_settings_attrs(obj.__class__):
                new_vals[attr] = opt.get(attr, getattr(obj, attr))
    return new_vals


def populate_config(filename, classes, from_file=True):
    '''Reads the config file and loads all the config data for the classes
    listed in `classes`.
    '''
    opts = {}
    if from_file:
        try:
            with open(filename) as fh:
                opts = yaml_loads(fh.read())
            if opts is None:
                opts = {}
        except IOError:
            pass

    new_opts = {}
    for name, cls in classes.items():
        if isinstance(cls, dict):
            new_opts[name] = {
                k: _get_config_dict(k, c, opts.get(name, {})) for
                k, c in cls.items()}
        elif isinstance(cls, (list, tuple)):
            new_opts[name] = [_get_config_dict(name, c, opts) for c in cls]
        else:
            new_opts[name] = _get_config_dict(name, cls, opts)
    return new_opts


def apply_config(opts, classes):
    '''Takes the config data read with :func:`populate_config` and applys
    them to any existing class instances listed in classes.
    '''
    for name, cls in classes.items():
        if name not in opts:
            continue

        if isclass(cls):
            continue
        else:
            obj = cls

        if not obj:
            continue

        if hasattr(obj, 'apply_settings'):
            obj.apply_settings(opts[name])
        else:
            if hasattr(obj, 'apply_settings_attrs'):
                obj.apply_settings_attrs(opts[name])
            else:
                for k, v in opts[name].items():
                    setattr(obj, k, v)


def _whitesp_sub(m):
    return re.sub(config_whitesp_pat, '', m.group(0))


def dump_config(filename, data):
    # s = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
    # s = re.sub(config_list_pat, _whitesp_sub, s)
    with open(filename, 'w') as fh:
        fh.write(yaml_dumps(data))


def populate_dump_config(filename, classes, from_file=True):
    opts = populate_config(filename, classes, from_file=from_file)
    dump_config(filename, opts)
    return opts


def create_doc_listener(sphinx_app, package, filename='config_attrs.json'):
    """Creates a listener for the ``__settings_attrs__`` attributes and dumps
    the docs of any props listed to ``filename``. If the file
    already exists, it extends it with new data and overwrites any exiting
    properties that we see again in this run.

    To use, in the sphinx conf.py file do::

        def setup(app):
            import package
            create_doc_listener(
                app, package,
                os.environ.get('BASEKIVYAPP_CONFIG_DOC_PATH', 'config_attrs.json')
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
            if hasattr(obj, '__settings_attrs__'):
                # get all the baseclasses of this package of this class
                for c, attrs in _get_classses_settings_attrs(obj).items():
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


def get_config_attrs_doc(classes, filename='config_attrs.json'):
    """Objects is a dict of object (class) paths and keys are the names of the
    config attributes of the class.
    """
    # names of actual classes used
    docs_used = {}
    # mapping from module names to module instances
    packages = {}
    # dict mapping class name to the actual class
    flat_clsses = {}
    for name, cls in classes.items():
        if isinstance(cls, (list, tuple)):
            for i, c in enumerate(cls):
                flat_clsses['{} - {}'.format(name, i)] = c
        elif isinstance(cls, dict):
            for k, c in cls.items():
                flat_clsses['{} - {}'.format(name, k)] = c
        else:
            flat_clsses[name] = cls

    # get the modules associated with each of the classes
    for name, cls in flat_clsses.items():
        if not isclass(cls):
            cls = cls.__class__
        if not _get_settings_attrs(cls):
            continue

        # get all the parent classes of the class and their props
        docs_used[name] = _get_classses_settings_attrs(cls)
        for c in docs_used[name]:
            mod = c.split('.')[0]
            packages[mod] = import_module(mod)

    # get the saved docs
    with open(filename) as fh:
        docs = json.load(fh)

    # mapping of class name to a mapping of class props to their docs
    docs_final = {}
    for name, classes_attrs in docs_used.items():
        docs_final[name] = {}
        for cls, attrs in classes_attrs.items():
            cls_docs = docs.get(cls, {})
            for attr in attrs:
                attrs[attr][1] = cls_docs.get(attr, [])
            docs_final[name].update(attrs)
    return docs_final


def write_config_attrs_rst(
        classes, package, app, exception, filename='config_attrs.json',
        rst_fname=join('source', 'config.rst')):
    """Walks through all the configurable classes of this package
    (should be gotten from
    :meth:`~base_kivy_app.app.BaseKivyApp.get_config_classes` or
    :meth:`~base_kivy_app.app.BaseKivyApp.get_app_config_classes`) and loads the
    docs of those properties and generates a rst output file with all the
    tokens.

    For example in the sphinx conf.py file do::

        def setup(app):
            app.connect('build-finished', partial(write_config_attrs_rst, \
ProjectApp.get_config_classes(), project_name))

    where project_name is the project module and ProjectApp is the App of the
    package.
    """
    # get the docs for the props
    docs = get_config_attrs_doc(classes, filename)

    header = '{} Config'.format(package.__name__.upper())
    lines = [
        header, '=' * len(header), '',
        'The following are the configuration options provided by the app. '
        'It can be configured by changing appropriate values in the '
        '``config.yaml`` file. The options default to the default value '
        'in the classes configurable by these options.', '']

    for name, attrs in sorted(docs.items(), key=operator.itemgetter(0)):
        lines.append(name)
        lines.append('-' * len(name))
        lines.append('')
        for attr, (default, doc) in sorted(attrs.items(),
                                           key=operator.itemgetter(0)):
            if isinstance(default, str):
                lines.append('`{}`: "{}"'.format(attr, default))
            else:
                lines.append('`{}`: {}'.format(attr, default))
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
