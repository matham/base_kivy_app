"""App
========

The base App class.
"""

import os
import sys
from os.path import dirname, join, isdir, expanduser
from threading import Thread
from more_kivy_app.app import report_exception_in_app, app_error, \
    app_error_async, MoreKivyApp, run_app, run_app_async


if not os.environ.get('KIVY_DOC_INCLUDE', None):
    from kivy.config import Config
    Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

from kivy.properties import ObjectProperty, StringProperty
from kivy.resources import resource_add_path
from kivy.factory import Factory
from kivy.clock import Clock

from plyer import filechooser

import base_kivy_app.graphics  # required to load kv
from base_kivy_app.utils import ColorTheme
if not os.environ.get('KIVY_DOC_INCLUDE', None):
    Clock.max_iteration = 20

__all__ = ('BaseKivyApp', 'run_app', 'run_app_async', 'app_error',
           'app_error_async', 'report_exception_in_app')


class BaseKivyApp(MoreKivyApp):
    """The base app.
    """

    error_indicator = ObjectProperty(None)
    '''The error indicator that gets the error reports. The app GUI
    should set :attr:`error_indicator` to the
    :class:`BaseKivyApp.graphics.ErrorIndicator` instance used in the app
    abd it will be used to diplay errors and warnings.
    '''

    filebrowser = ObjectProperty(None)
    '''Stores a instance of :class:`PopupBrowser` that is automatically created
    by this app class. That class is described in ``base_kivy_app/graphics.kv``.
    '''

    theme = ObjectProperty(None, rebind=True)

    _close_popup = ObjectProperty(None)

    _close_message = StringProperty('Cannot close currently')

    def on__close_message(self, *largs):
        if self._close_popup is not None:
            self._close_popup.text = self._close_message

    def __init__(self, **kw):
        self.theme = ColorTheme()
        super(BaseKivyApp, self).__init__(**kw)
        resource_add_path(join(dirname(__file__), 'media'))
        resource_add_path(join(dirname(__file__), 'media', 'flat_icons'))

    def build_default_widgets(self):
        self._close_popup = Factory.ClosePopup()

    def init_load(self):
        self.build_default_widgets()
        if self._close_popup is not None:
            self._close_popup.text = self._close_message

        super().init_load()

    def ask_cannot_close(self, *largs, **kwargs):
        if not self.check_close():
            if self._close_message:
                if self._close_popup is not None:
                    self._close_popup.open()
            return True
        return False

    def check_close(self):
        """Returns whether the app can close now. Otherwise, a message telling
        the user it cannot close now with message :attr:`_close_message` will
        be shown.
        """
        return True

    def open_filechooser(
            self, callback, target=expanduser('~'), dirselect=False,
            multiselect=False, mode='open', title='', filters=()):
        if not os.path.exists(target):
            target = expanduser('~')

        def _callback(paths):
            def _inner_callback(*largs):
                callback(paths)
            Clock.schedule_once(_inner_callback)

        def re_enable(*args):
            self.root.disabled = False

        def run_thread():
            try:
                if dirselect:
                    filechooser.choose_dir(
                        path=target, multiple=multiselect,
                        title=title or 'Pick a directory...',
                        on_selection=_callback, filters=filters)
                elif mode == 'open':
                    filechooser.open_file(
                        path=target, multiple=multiselect,
                        title=title or 'Pick a file...',
                        on_selection=_callback, filters=filters)
                else:
                    filechooser.save_file(
                        path=target, multiple=multiselect,
                        title=title or 'Pick a file...',
                        on_selection=_callback, filters=filters)
            finally:
                Clock.schedule_once(re_enable)

        self.root.disabled = True
        if sys.platform == 'darwin':
            filters = ()
            run_thread()
        else:
            thread = Thread(target=run_thread)
            thread.start()
