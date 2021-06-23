'''Graphics
============
'''
from os.path import join, dirname
import math
from time import perf_counter
from functools import partial
from inspect import isclass
from math import pow, fabs

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import (
    NumericProperty, ReferenceListProperty, ObjectProperty,
    ListProperty, StringProperty, BooleanProperty, DictProperty, AliasProperty,
    OptionProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scatter import Scatter
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.graphics.texture import Texture
from kivy.graphics import Rectangle, BindTexture
from kivy.graphics.transformation import Matrix
from kivy.graphics.fbo import Fbo
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.behaviors.button import ButtonBehavior
from kivy.uix.behaviors.focus import FocusBehavior
from kivy.animation import Sequence, Animation
from kivy.factory import Factory
from kivy.compat import string_types
from kivy.uix.dropdown import DropDown
from kivy.uix.textinput import TextInput
from kivy.uix.slider import Slider

from base_kivy_app.utils import pretty_time

__all__ = (
    'EventFocusBehavior', 'BufferImage', 'TimeLineSlice',
    'TimeLine', 'AutoSizedSpinner', 'EmptyDropDown', 'HighightButtonBehavior')


Builder.load_file(join(dirname(__file__), 'graphics.kv'))


class AutoSizedSpinnerBehavior(object):
    '''Spinner that exposes :attr:`minimum_size`, which is the size
    required to display the texture of the largest item in the spinner.
    '''

    minimum_size = ObjectProperty((0, 0))
    '''A 2-tuple containing the texture width and height of the spinner item
    with the largest texture. Can be used to set the spinner size to ensure it
    will be big enough to display nicely the largest item.
    '''

    def __init__(self, **kwargs):
        cls = kwargs.pop('option_cls', self.option_cls)
        if isinstance(cls, string_types):
            cls = Factory.get(cls)
        self.option_cls = partial(self._decorate_class, cls)

        def decorate_cls(*largs):
            cls = self.option_cls
            if isinstance(cls, string_types):
                cls = Factory.get(cls)

            if not isclass(cls) or not issubclass(cls, Widget):
                return
            self.option_cls = partial(self._decorate_class, cls)
        self.fbind('option_cls', decorate_cls)
        self.fbind('texture_size', self._update_min_size)
        self.fbind('padding', self._update_min_size)

        super(AutoSizedSpinnerBehavior, self).__init__(**kwargs)
        self._update_min_size()

    def _decorate_class(self, cls, *l, **kw):
        wid = cls(*l, **kw)
        wid.fbind('texture_size', self._update_min_size)
        self._update_min_size()
        return wid

    def _update_min_size(self, *largs):
        if not self._dropdown or not self._dropdown.container:
            widgets = [self]
        else:
            widgets = self._dropdown.container.children + [self]

        w = max((c.texture_size[0] for c in widgets))
        h = max((c.texture_size[1] for c in widgets))

        self.minimum_size = w + 2 * self.padding_x, h + 2 * self.padding_y


class EmptyDropDown(DropDown):

    def __init__(self, **kwargs):
        super(EmptyDropDown, self).__init__(container=None, **kwargs)


class FollowingLabel(Label):

    attached_widget = None

    def show_label(self, widget):
        self.attached_widget = widget
        Window.add_widget(self)
        widget.fbind('center', self._reposition)
        self.fbind('size', self._reposition)
        self._reposition()

    def hide_label(self):
        Window.remove_widget(self)
        self.attached_widget.funbind('center', self._reposition)
        self.funbind('size', self._reposition)

    def _reposition(self, *largs):
        # calculate the coordinate of the attached widget in the window
        # coordinate system
        win = Window
        widget = self.attached_widget
        wx, wy = widget.to_window(*widget.pos)
        _, wtop = widget.to_window(widget.right, widget.top)

        # ensure it doesn't get out on the X axis, with a
        # preference to 0 in case the list is too wide.
        x = wx
        if x + self.width > win.width:
            x = win.width - self.width
        if x < 0:
            x = 0
        self.x = x

        # determine if we display upper or lower to the widget
        height = self.height

        h_bottom = wy - height
        h_top = win.height - (wtop + height)
        if h_bottom > 0:
            self.y = h_bottom
        elif h_top > 0:
            self.y = wtop
        else:
            if h_top < h_bottom:
                self.top = self.height = wy
            else:
                self.y = wtop


Builder.load_string('''
<FollowingLabel>:
    size_hint: None, None
    size: self.texture_size
    padding: '6dp', '6dp'
    color: 0, 0, 0, 1
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            size: self.size
            pos: self.pos

<HighightButtonBehavior>:
    canvas.after:
        Color:
            a: .3 if self.hovering else 0
        Rectangle:
            pos: self.pos
            size: self.size
''')


class HighightButtonBehavior(object):

    show_hover = BooleanProperty(True)

    hover_text = StringProperty('')

    hovering = BooleanProperty(False)

    attached_widget = None

    tracked_widgets = []

    label = None

    def __init__(self, **kwargs):
        super(HighightButtonBehavior, self).__init__(**kwargs)
        if self.show_hover:
            self.tracked_widgets.append(self.proxy_ref)

    def on_show_hover(self, *largs):
        if self.show_hover:
            self.tracked_widgets.append(self.proxy_ref)
        else:
            if self.hovering:
                self.detach_widget()
            self.tracked_widgets.remove(self.proxy_ref)

    def on_hover_text(self, *largs):
        if self.hovering and self.label:
            self.label.text = self.hover_text

    @staticmethod
    def init_class():
        Window.fbind('mouse_pos', HighightButtonBehavior.track_mouse)
        HighightButtonBehavior.label = FollowingLabel(markup=True)

    @staticmethod
    def uninit_class():
        Window.funbind('mouse_pos', HighightButtonBehavior.track_mouse)
        HighightButtonBehavior.label = None
        HighightButtonBehavior.attached_widget = None
        del HighightButtonBehavior.tracked_widgets[:]

    def attach_widget(self):
        self.hovering = True
        if self.hover_text and self.label is not None:
            self.label.show_label(self)
            self.label.text = self.hover_text
        HighightButtonBehavior.attached_widget = self

    def detach_widget(self):
        self.hovering = False
        HighightButtonBehavior.attached_widget = None
        if self.hover_text and self.label is not None:
            self.label.hide_label()

    @staticmethod
    def track_mouse(instance, pos):
        widget = HighightButtonBehavior.attached_widget
        if widget:
            if widget.collide_point(*widget.to_parent(*widget.to_widget(*pos))):
                return
            else:
                widget.detach_widget()

        for widget in HighightButtonBehavior.tracked_widgets:
            try:
                if widget.collide_point(
                        *widget.to_parent(*widget.to_widget(*pos))):
                    widget.attach_widget()
                    break
            except ReferenceError:
                pass


class SpinnerBehavior(AutoSizedSpinnerBehavior):

    values = ListProperty()

    text_autoupdate = BooleanProperty(False)

    option_cls = ObjectProperty(SpinnerOption)

    dropdown_cls = ObjectProperty(DropDown)

    is_open = BooleanProperty(False)

    sync_height = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._dropdown = None
        super(SpinnerBehavior, self).__init__(**kwargs)
        fbind = self.fbind
        build_dropdown = self._build_dropdown
        fbind('on_release', self._toggle_dropdown)
        fbind('dropdown_cls', build_dropdown)
        fbind('option_cls', build_dropdown)
        fbind('values', self._update_dropdown)
        fbind('size', self._update_dropdown_size)
        fbind('text_autoupdate', self._update_dropdown)
        build_dropdown()

    def _build_dropdown(self, *largs):
        if self._dropdown:
            self._dropdown.unbind(on_select=self._on_dropdown_select)
            self._dropdown.unbind(on_dismiss=self._close_dropdown)
            self._dropdown.dismiss()
            self._dropdown = None
        cls = self.dropdown_cls
        if isinstance(cls, string_types):
            cls = Factory.get(cls)
        self._dropdown = cls()
        self._dropdown.bar_width = '10dp'
        self._dropdown.scroll_type = ['bars']
        self._dropdown.bind(on_select=self._on_dropdown_select)
        self._dropdown.bind(on_dismiss=self._close_dropdown)
        self._update_dropdown()

    def _update_dropdown_size(self, *largs):
        if not self.sync_height:
            return
        dp = self._dropdown
        if not dp:
            return

        container = dp.container
        if not container:
            return
        h = self.height
        for item in container.children[:]:
            item.height = h

    def _update_dropdown(self, *largs):
        dp = self._dropdown
        cls = self.option_cls
        values = self.values
        text_autoupdate = self.text_autoupdate
        if isinstance(cls, string_types):
            cls = Factory.get(cls)
        dp.clear_widgets()
        for value in values:
            item = cls(text=value)
            item.height = self.height if self.sync_height else item.height
            item.bind(on_release=lambda option: dp.select(option.text))
            dp.add_widget(item)
        if text_autoupdate:
            if values:
                if not self.text or self.text not in values:
                    self.text = values[0]
            else:
                self.text = ''

    def _toggle_dropdown(self, *largs):
        if self.values:
            self.is_open = not self.is_open

    def _close_dropdown(self, *largs):
        self.is_open = False

    def _on_dropdown_select(self, instance, data, *largs):
        self.text = data
        self.is_open = False

    def on_is_open(self, instance, value):
        if value:
            self._dropdown.open(self)
        else:
            if self._dropdown.attach_to:
                self._dropdown.dismiss()


class AutoSizedSpinner(AutoSizedSpinnerBehavior, Spinner):
    pass


class EventFocusBehavior(FocusBehavior):
    ''':class:`~kivy.uix.behaviors.focus.FocusBehavior` based class which
    converts keyboard events listed in :attr:`keys` into a ``on_key_press`` or
    ``on_key_release`` event.

    :Events:

        `on_key_press`:
            Triggered when a key that is in :attr:`keys` is pressed.
        `on_key_release`:
            Triggered when a key that is in :attr:`keys` is released.
    '''

    __events__ = ('on_key_press', 'on_key_release')

    keys = ListProperty(['spacebar', 'escape', 'enter'])
    '''A list of strings that are potential keyboard keys, which trigger
    key press or key release events.

    Defaults to `['spacebar', 'escape', 'enter']`.
    '''

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        if super(EventFocusBehavior, self).keyboard_on_key_down(
                window, keycode, text, modifiers):
            return True
        if keycode[1] in self.keys:
            return self.dispatch('on_key_press', keycode[1])

    def keyboard_on_key_up(self, window, keycode):
        if super(EventFocusBehavior, self).keyboard_on_key_up(window, keycode):
            return True
        if keycode[1] in self.keys:
            return self.dispatch('on_key_release', keycode[1])

    def on_key_press(self, key):
        pass

    def on_key_release(self, key):
        pass


class BufferImage(Scatter):
    '''Class that displays an image and allows its manipulation using touch.
    It receives an ffpyplayer :py:class:`~ffpyplayer.pic.Image` object.
    '''

    scale_to_image = BooleanProperty(True)

    flip = BooleanProperty(False)

    _iw = NumericProperty(0.)
    '''The width of the input image. '''

    _ih = NumericProperty(0.)
    '''The height of the input image. '''

    available_size = ObjectProperty(None, allownone=True)
    '''The size that the widget has available for drawing.
    '''

    _last_w = 0
    '''The width of the screen region available to display the image. Can be
    used to determine if the screen size changed and we need to output a
    different sized image.
    '''

    _last_h = 0
    '''The width of the screen region available to display the image. '''

    _last_rotation = 0

    image_size = ObjectProperty((0, 0))
    '''The size of the last image.
    '''

    _fmt = ''
    '''The input format of the last image passed in, if the format is
    supported. E.g. rgb24, yuv420p, etc. Otherwise, it's the forma into which
    the unsupported image is converted into.
    '''

    _sw_src_fmt = ''
    '''The input format of the last image passed in. '''

    _swscale = None
    '''The SWScale object that converts the image into a supported format. '''

    img = None
    '''Holds the last :class:`~ffpyplayer.pic.Image` passed in. '''

    texture_size = ObjectProperty((0, 0))
    '''A tuple with the size of the last :class:`~ffpyplayer.pic.Image`
    that was passed in.
    '''

    img_texture = ObjectProperty(None, allownone=True)
    '''The texture into which the images are blitted. Defaults to None. '''

    color = ListProperty([1, 1, 1, 1])
    '''The color in which to display the image. '''

    _kivy_ofmt = ''
    '''Kivy's color format of the image passed in. '''

    _tex_y = None
    ''' The y texture into which the y plane of the images are blitted when
    yuv420p.
    '''

    _tex_u = None
    ''' The u texture into which the u plane of the images are blitted when
    yuv420p.
    '''

    _tex_v = None
    ''' The v texture into which the v plane of the images are blitted when
    yuv420p.
    '''

    _fbo = None
    ''' The Fbo used when blitting yuv420p images. '''

    _YUV_RGB_FS = '''
    $HEADER$
    uniform sampler2D tex_y;
    uniform sampler2D tex_u;
    uniform sampler2D tex_v;

    void main(void) {
        float y = texture2D(tex_y, tex_coord0).r;
        float u = texture2D(tex_u, tex_coord0).r - 0.5;
        float v = texture2D(tex_v, tex_coord0).r - 0.5;
        float r = y + 1.402 * v;
        float g = y - 0.344 * u - 0.714 * v;
        float b = y + 1.772 * u;
        gl_FragColor = vec4(r, g, b, 1.0);
    }
    '''

    def on_flip(self, *largs):
        self.update_img(self.img, True)

    def update_img(self, img, force=False):
        ''' Updates the screen with a new image.

        :Parameters:

            `img`: :class:`~ffpyplayer.pic.Image` instance
                The image to be displayed.
        '''
        from ffpyplayer.tools import get_best_pix_fmt
        from ffpyplayer.pic import SWScale
        if img is None:
            return

        img_fmt = img.get_pixel_format()
        self.image_size = img_w, img_h = img.get_size()

        update = force
        if self._iw != img_w or self._ih != img_h:
            update = True

        if img_fmt not in ('yuv420p', 'rgba', 'rgb24', 'gray', 'bgr24', 'bgra'):
            swscale = self._swscale
            if img_fmt != self._sw_src_fmt or swscale is None or update:
                ofmt = get_best_pix_fmt(
                    img_fmt, (
                        'yuv420p', 'rgba', 'rgb24', 'gray', 'bgr24', 'bgra'))
                self._swscale = swscale = SWScale(
                    iw=img_w, ih=img_h, ifmt=img_fmt, ow=0, oh=0, ofmt=ofmt)
                self._sw_src_fmt = img_fmt
            img = swscale.scale(img)
            img_fmt = img.get_pixel_format()

        w, h = self.available_size or self.size
        if (not w) or not h:
            self.img = img
            return

        if self._fmt != img_fmt:
            self._fmt = img_fmt
            self._kivy_ofmt = {
                'yuv420p': 'yuv420p', 'rgba': 'rgba', 'rgb24': 'rgb',
                'gray': 'luminance', 'bgr24': 'bgr', 'bgra': 'bgra'}[img_fmt]
            update = True

        if update or w != self._last_w or h != self._last_h or \
                self.rotation != self._last_rotation:
            if self.scale_to_image:
                rotation = self.rotation
                rot = self.rotation * math.pi / 180
                rot_w = abs(img_w * math.cos(rot)) + abs(img_h * math.sin(rot))
                rot_h = abs(img_h * math.cos(rot)) + abs(img_w * math.sin(rot))
                scalew, scaleh = w / rot_w, h / rot_h
                scale = min(min(scalew, scaleh), 1)
                self.transform = Matrix()
                self.rotation = rotation
                self.apply_transform(Matrix().scale(scale, scale, 1),
                                     post_multiply=True)
                self.pos = 0, 0
            self._iw, self._ih = img_w, img_h
            self._last_h = h
            self._last_w = w
            self._last_rotation = self.rotation

        self.img = img
        kivy_ofmt = self._kivy_ofmt

        if update:
            self.canvas.remove_group(str(self) + 'image_display')
            if kivy_ofmt == 'yuv420p':
                w2 = int(img_w / 2)
                h2 = int(img_h / 2)
                self._tex_y = Texture.create(size=(img_w, img_h),
                                             colorfmt='luminance')
                self._tex_u = Texture.create(size=(w2, h2),
                                             colorfmt='luminance')
                self._tex_v = Texture.create(size=(w2, h2),
                                             colorfmt='luminance')
                with self.canvas:
                    self._fbo = fbo = Fbo(size=(img_w, img_h),
                                          group=str(self) + 'image_display')
                with fbo:
                    BindTexture(texture=self._tex_u, index=1)
                    BindTexture(texture=self._tex_v, index=2)
                    Rectangle(size=fbo.size, texture=self._tex_y)
                fbo.shader.fs = BufferImage._YUV_RGB_FS
                fbo['tex_y'] = 0
                fbo['tex_u'] = 1
                fbo['tex_v'] = 2
                tex = self.img_texture = fbo.texture
                fbo.add_reload_observer(self.reload_buffer)
            else:
                tex = self.img_texture = Texture.create(
                    size=(img_w, img_h), colorfmt=kivy_ofmt)
                tex.add_reload_observer(self.reload_buffer)

            tex.flip_vertical()
            if self.flip:
                tex.flip_horizontal()
            self.texture_size = img_w, img_h

        if kivy_ofmt == 'yuv420p':
            dy, du, dv, _ = img.to_memoryview()
            self._tex_y.blit_buffer(dy, colorfmt='luminance')
            self._tex_u.blit_buffer(du, colorfmt='luminance')
            self._tex_v.blit_buffer(dv, colorfmt='luminance')
            self._fbo.ask_update()
            self._fbo.draw()
        else:
            self.img_texture.blit_buffer(img.to_memoryview()[0],
                                         colorfmt=kivy_ofmt)
            self.canvas.ask_update()

    def reload_buffer(self, *args):
        ''' Reloads the last displayed image. It is and should be called
        whenever the screen size changes or the last image need to be
        recalculated.
        '''
        if self.img is not None:
            self.update_img(self.img)

    def rotate_right_reposition(self):
        rotation = self.rotation - 90
        factor = abs(int(round(rotation / 90))) % 4
        self.rotation = math.copysign(factor * 90, rotation)
        self.reload_buffer()

    def clear_image(self):
        self.canvas.remove_group(str(self) + 'image_display')
        self.img_texture = None
        self.texture_size = 0, 0
        self._fmt = ''
        self.img = None
        self.canvas.ask_update()


class ErrorIndicatorBehavior(ButtonBehavior):
    '''A Button based class that visualizes and notifies on the current error
    status.

    When pressed, it stops the notification and displays in a popup the list
    of errors/warnings/infos.

    Errors are added to the log with :meth:`add_item.`
    '''

    _container = None

    _level = StringProperty('ok')

    _alpha = NumericProperty(1.)

    _anim = None

    levels = {'error': 0, 'warning': 1, 'info': 2}

    icon_names = {}

    count = NumericProperty(0)

    __events__ = ('on_log_event', )

    def __init__(self, **kw):
        super(ErrorIndicatorBehavior, self).__init__(**kw)
        a = self._anim = Sequence(
            Animation(t='in_bounce', _alpha=1.),
            Animation(t='out_bounce', _alpha=0))
        a.repeat = True

    def add_item(self, text, level='error'):
        '''Adds a log item to the log. Upon addition, the button will notify
        with an animation of the item.

        :Parameters:

            `text`: str
                The text of the item.
            `level`: str
                Can be one of `error`, `warning`, or `info` indicating
                the importance of the item. Defaults to `error`.
        '''
        levels = self.levels
        if level not in levels:
            raise ValueError('"{}" is not a valid level within "{}"'.
                             format(level, levels.keys()))

        self.count += 1
        if self._level == 'ok':
            if levels[level] < levels['info']:
                self._level = level
                self._anim.start(self)
        elif levels[level] < levels[self._level]:
            self._level = level

        self._container.data.append(
            {'text': text, 'icon_name': self.icon_names.get(level, level)})
        self.dispatch('on_log_event', self, text, level)

    def on_log_event(self, *largs):
        pass


class TimeLineSlice(Widget):
    '''A representation of a time slice of :class:`TimeLine`.
    '''

    duration = NumericProperty(0)
    '''The duration of the slice.
    '''

    elapsed_t = NumericProperty(0)
    '''The amount of time that has elapsed since the start of this slice.
    Can be larger than :attr:`duration`, but visually it gets clipped to
    :attr:`duration`.
    '''

    _scale = NumericProperty(0)

    color = ObjectProperty(None, allownone=True)
    '''If not None, it's a list of size 2 indicating the color to use for when
    the slice is not yet done and when it's done, respectively. When not None,
    it overwrites the values provided with :attr:`TimeLine.color_odd` and
    ::`attr.color_even`.
    '''

    _color = ListProperty([(1, 1, 1, 1), (1, 1, 1, 1)])

    name = StringProperty('')
    '''The name of the slice.
    '''

    text = StringProperty('')
    '''If not empty, rather than displaying :attr:`name` when this slice is
    active, it'll display this :attr:`text`.
    '''


class TimeLine(BoxLayout):
    '''A widget that displays an elapsing time line. It has named time slices
    indicating e.g. timed stages and the time line progresses through them.

    Slices are added/removed with :meth:`add_slice`, :meth:`remove_slice`, and
    :meth:`clear_slices`. :meth:`smear_slices` is used to smear the width
    of the slices so that they are non-linearly proportional to the provided
    duration of each slice.

    To move from one slice to another, :meth:`set_active_slice` must be called.
    It sets all the previous slices preceding this slice as done. Slices do not
    automatically finish, without this method being called.

    Properties of
    '''

    slices = ListProperty([])
    '''The list of :class:`TimeLineSlice` visualizing all the slices.
    '''

    slice_names = ListProperty([])
    '''The given name corresponding to the slices in :attr:`slices`. They
    should be unique.
    '''

    current_slice = NumericProperty(None, allownone=True)
    '''The index in :attr:`slices` that is the current slice.
    '''

    timer = StringProperty('')
    '''A string version of the amount of time elapsed within the current slice.
    It gets reset when :meth:`set_active_slice` is called.
    '''

    text = StringProperty('')
    '''The name of the current slice displayed in the status field. '''

    color_odd = ListProperty([(0, .7, .2, 1), (.5, .5, 0, 1)])
    '''A list of size 2 indicating the color to use when the slice is not yet
    done and when it's done for odd slices, respectively. Each item is a 4
    tuple indicating the rgba value (0-1) to use.
    '''

    color_even = ListProperty(
        [(0, .2, .7, 1), (135 / 255., 206 / 255., 250 / 255., 1)])
    '''A list of size 2 indicating the color to use when the slice is not yet
    done and when it's done for even slices, respectively. Each item is a 4
    tuple indicating the rgba value (0-1) to use.
    '''

    _start_t = perf_counter()

    def __init__(self, **kwargs):
        super(TimeLine, self).__init__(**kwargs)
        Clock.schedule_interval(self._update_clock, .15)

    def _update_clock(self, dt):
        elapsed = perf_counter() - self._start_t
        self.timer = pretty_time(elapsed)
        if self.slices and self.current_slice is not None:
            self.slices[self.current_slice].elapsed_t = elapsed

    def set_active_slice(self, name, after=None):
        '''Sets the slice that is the active slice. All the slices preceding
        this slice will be marked as done and the timer will restart.

        :Parameters:

            `name`: str
                The name of the slice to set as the current slice. It can be
                the name of a non-existing slice.
            `after`: str
                If ``name`` is a non-existing slice, if ``after`` is None,
                then all the slices preceding, and including the current slice
                will be marked as done. Otherwise, all the slices preceding
                and including the named slice will be marked as done.
        '''
        try:
            idx = self.slice_names.index(name)
            for s in self.slices[:idx]:
                s.elapsed_t = max(s.duration, 10000)
            for s in self.slices[idx:]:
                s.elapsed_t = 0.
            self.current_slice = idx
        except ValueError:
            if after is not None:
                idx = self.slice_names.index(after)
                for s in self.slices[:idx + 1]:
                    s.elapsed_t = max(s.duration, 10000)
                for s in self.slices[idx + 1:]:
                    s.elapsed_t = 0.
            elif self.current_slice is not None:
                for s in self.slices[:self.current_slice + 1]:
                    s.elapsed_t = max(s.duration, 10000)
            self.current_slice = None
            self.text = name
        self._start_t = perf_counter()

    def clear_slices(self):
        '''Removes all the slices and clears the time line.
        '''
        for ch in self.box.children[:]:
            self.box.remove_widget(ch)
        self.current_slice = None
        self.slice_names = []
        self.slices = []
        self._start_t = perf_counter()

    def update_slice_attrs(self, current_name, **kwargs):
        '''Called to update the attributes of the :class:`TimeLineSlice`
        instance associated with the name such as
        :attr:`TimeLineSlice.duration` etc. Can be used to even rename the
        slice.

        :Parameters:

            `name`: str
                The name of the slice to update.
            `**kwargs`: keyword args
                The names and values of the slice to change.
        '''
        s = self.slices[self.slice_names.index(current_name)]
        for key, val in kwargs.items():
            setattr(s, key, val)
        self._update_attrs()

    def _update_attrs(self):
        widgets = list(reversed(self.box.children))
        self.slice_names = [widget.name for widget in widgets]
        for i, wid in enumerate(widgets):
            wid._color = self.color_odd if i % 2 else self.color_even

    def add_slice(
            self, name, before=None, duration=0, size_hint_x=None, **kwargs):
        '''Adds a new slice to the timeline.

        :Parameters:

            `name`: str
                The unique name of the new slice to create.
            `before`: str
                If not None, the name of the slice before which to create the
                new slice. Otherwise, the default, it's added at the end.
            `duration`: float, int
                The estimated duration of the slice. Defaults to 0. A slice
                of duration 0 is allowed.
            `size_hint_x`: float
                The width size_hint of the slice display. If None, the default,
                the duration is used as the size hint, otherwise the provided
                value is used. Since Kivy normalizes the size hints to 1.0, by
                default the duration is used to scale the displayed width of
                the slices to their durations.
        '''
        if 'text' not in kwargs:
            kwargs['text'] = name
        s = TimeLineSlice(
            duration=duration, name=name,
            size_hint_x=size_hint_x if size_hint_x is not None else duration,
            **kwargs)
        if before is not None:
            i = self.slice_names.index(before)
            old_len = len(self.slices)
            self.slices.insert(s, i)
            i = old_len - i
        else:
            self.slices.append(s)
            i = 0
        self.box.add_widget(s, index=i)
        self._update_attrs()

    def remove_slice(self, name):
        '''Removes the named slice.

        :Parameters:

            `name`: str
                The name of the slice to remove.
        '''
        s = self.slices.pop(self.slice_names.index(name))
        self.box.remove_widget(s)
        self._update_attrs()

    def smear_slices(self, exponent=3):
        '''Smears the width of the slices in a non-linear manner so that the
        width of each slice become less exactly related to the duration of
        the slice. It is useful to prevent some slices being huge and other
        tiny.

        Overall, the algorithm normalizes exponentiated durations to their mean
        exponentiated value.

        :Parameters:

            `exponent`: float, int
                The exponent to use when smearing the slices. Defaults to 3.
        '''
        widgets = self.box.children
        vals = [w.duration for w in widgets if w.duration]
        mn, mx = min(vals), max(vals)
        center = (mn + mx) / 2.
        a = pow(mx - center, exponent)
        offset = abs(pow(mn - center, exponent) / a)

        def f(x):
            return max((2 * pow(x - center, exponent) / a) + offset, offset)

        for w in widgets:
            w.size_hint_x = f(w.duration)


class FlatTextInput(TextInput):
    pass


class TimeSliceSelection(Widget):

    low_handle = NumericProperty(0)

    high_handle = NumericProperty(1)

    min = NumericProperty(0)

    max = NumericProperty(1)

    low_val = NumericProperty(0)

    high_val = NumericProperty(1)

    _working = False

    def __init__(self, **kwargs):
        super(TimeSliceSelection, self).__init__(**kwargs)
        self.fbind('min', self._update_handles)
        self.fbind('max', self._update_handles)
        self.fbind('width', self._update_handles)
        self.fbind('x', self._update_handles)
        self.fbind('low_val', self._update_handles)
        self.fbind('high_val', self._update_handles)

    def _update_handles(self, *largs):
        if self._working:
            return

        lowval = self.low_val
        highval = self.high_val
        mn = self.min
        mx = self.max

        if lowval < mn:
            self.low_val = mn
            return
        if highval > mx:
            self.high_val = mx
            return

        if lowval > highval:
            self._working = True
            self.low_val = highval
            self._working = False
            self.high_val = lowval
            return

        self.low_handle = self.to_size(lowval - mn) + self.x
        self.high_handle = self.to_size(highval - mn) + self.x

    def to_size(self, value):
        '''value is the state value. returns in size.
        '''
        diff = float(self.max - self.min)
        w = self.width

        if not diff or not w:
            return 0
        return value / diff * w

    def to_state(self, value):
        '''value is the size value. returns in state.
        '''
        diff = float(self.max - self.min)
        w = float(self.width)

        if not diff or not w:
            return 0
        return value / w * diff

    def on_touch_down(self, touch):
        if super(TimeSliceSelection, self).on_touch_down(touch):
            return True

        if not self.collide_point(*touch.pos):
            return False

        tol = dp(2)
        if self.low_handle - tol <= touch.x <= self.high_handle + tol:
            if self.low_handle + tol <= touch.x <= self.high_handle - tol:
                touch.ud['{0}.{1}'.format('timeslice', self.uid)] = 'center'
            else:
                touch.ud['{0}.{1}'.format('timeslice', self.uid)] = 'side'
            return True
        return False

    def on_touch_move(self, touch):
        if super(TimeSliceSelection, self).on_touch_move(touch):
            return True

        drag_type = touch.ud.get('{0}.{1}'.format('timeslice', self.uid))
        if drag_type not in ('center', 'side'):
            return False

        dx = touch.dx
        start = touch.x - dx
        positive = dx > 0
        tol = dp(2)
        diff = self.to_state(dx)

        if drag_type == 'center':
            if self.low_handle <= start <= self.high_handle:
                if positive:
                    diff = min(diff, self.max - self.high_val)
                    self.high_val += diff  # right side should move first
                    self.low_val += diff
                else:
                    diff = max(diff, self.min - self.low_val)
                    self.low_val += diff  # left side should move first
                    self.high_val += diff
            return True

        is_low = self.low_handle - tol <= start <= self.low_handle + tol
        is_high = self.high_handle - tol <= start <= self.high_handle + tol
        if is_low and is_high:
            if self.low_handle == self.high_handle:
                if positive:
                    is_low = False
                else:
                    is_high = False
            else:
                if fabs(self.low_handle - start) <= \
                        fabs(self.high_handle - start):
                    is_high = False
                else:
                    is_low = False

        if is_low:
            self.low_val = min(
                max(self.min, self.low_val + diff), self.high_val)
        else:
            self.high_val = min(
                max(self.low_val, self.high_val + diff), self.max)


class FlatSlider(Slider):

    __events__ = ('on_release', )

    def on_release(self, *largs):
        pass

    def on_touch_up(self, touch):
        if super(FlatSlider, self).on_touch_up(touch):
            if touch.grab_current == self:
                self.dispatch('on_release', self)
            return True


Factory.register('AutoSizedSpinnerBehavior', cls=AutoSizedSpinnerBehavior)
Factory.register('SpinnerBehavior', cls=SpinnerBehavior)
Factory.register('EventFocusBehavior', cls=EventFocusBehavior)
Factory.register('ErrorIndicatorBehavior', cls=ErrorIndicatorBehavior)
Factory.register('HighightButtonBehavior', cls=HighightButtonBehavior)
