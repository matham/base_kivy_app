'''Utilities
=============
'''
from kivy.utils import get_color_from_hex
from kivy.properties import StringProperty, ObservableDict, ObservableList, \
    Property
from kivy.factory import Factory
from kivy.event import EventDispatcher
from kivy.weakproxy import WeakProxy
from functools import partial
import json
from io import StringIO
from tree_config.utils import yaml_loads, get_yaml as orig_get_yaml, \
    yaml_dumps as orig_yaml_dumps

__all__ = ('pretty_time', 'pretty_space', 'json_dumps',
           'json_loads', 'ColorTheme', 'apply_args_post', 'yaml_dumps',
           'yaml_loads')


def pretty_time(seconds):
    '''Returns a nice representation of a time value.

    :Parameters:

        `seconds`: float, int
            The number, in seconds, to convert to a string.

    :returns:
        String representation of the time.

    For example::

        >>> pretty_time(36574)
        '10:9:34.0'
    '''
    seconds = int(seconds * 10)
    s, ms = divmod(seconds, 10)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return '{0:d}:{1:d}:{2:d}.{3:d}'.format(h, m, s, ms)
    elif m:
        return '0:{0:d}:{1:d}.{2:d}'.format(m, s, ms)
    else:
        return '0:0:{0:d}.{1:d}'.format(s, ms)


def pretty_space(space, is_rate=False):
    '''Returns a nice string representation of a number representing either
    size, e.g. 10 MB, or rate, e.g. 10 MB/s.

    :Parameters:

        `space`: float, int
            The number to convert.
        `is_rate`: bool
            Whether the number represents size or rate. Defaults to False.

    :returns:
        String representation of the space.

    For example::

        >>> pretty_space(10003045065)
        '9.32 GB'
        >>> tools.pretty_space(10003045065, is_rate=True)
        '9.32 GB/s'
    '''
    t = '/s' if is_rate else ''
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if space < 1024.0:
            return "%3.2f %s%s" % (space, x, t)
        space /= 1024.0
    return "%3.2f %s%s" % (space, 'TB', t)


def json_dumps(value):
    return json.dumps(value, sort_keys=True, indent=4, separators=(',', ': '))


def json_loads(value):
    return json.loads(value)


def represent_property(representer, data: Property):
    return representer.represent_data(data.defaultvalue)


def get_yaml():
    yaml = orig_get_yaml()
    yaml.default_flow_style = False

    yaml.representer.add_multi_representer(
        ObservableList, yaml.representer.__class__.represent_list)
    yaml.representer.add_multi_representer(
        ObservableDict, yaml.representer.__class__.represent_dict)

    yaml.representer.add_multi_representer(Property, represent_property)
    return yaml


yaml_dumps = partial(orig_yaml_dumps, get_yaml_obj=get_yaml)


class ColorTheme(EventDispatcher):
    '''Default values from https://www.materialpalette.com/amber/indigo
    '''

    primary_dark = StringProperty(get_color_from_hex('FFA000FF'))

    primary = StringProperty(get_color_from_hex('FFC107FF'))

    primary_light = StringProperty(get_color_from_hex('FFECB3FF'))

    primary_text = StringProperty(get_color_from_hex('FFFFFFFF'))
    '''This is different.
    '''

    accent = StringProperty(get_color_from_hex('536DFEFF'))

    text_primary = StringProperty(get_color_from_hex('212121FF'))

    text_secondary = StringProperty(get_color_from_hex('757575FF'))

    divider = StringProperty(get_color_from_hex('BDBDBDFF'))

    @staticmethod
    def interpolate(color1, color2, fraction):
        color = []
        for c1, c2 in zip(color1, color2):
            c = min(max((c2 - c1) * fraction + c1, 0), 1)
            color.append(c)
        return color


class KVBehavior(object):
    pass


def apply_args_post(cls, **keywordargs):
    def ret_func(*largs, **kwargs):
        o = cls(*largs, **kwargs)
        for key, value in keywordargs.items():
            setattr(o, key, value)
        return o
    return ret_func


Factory.register(classname='ColorTheme', cls=ColorTheme)
Factory.register(classname='KVBehavior', cls=KVBehavior)
