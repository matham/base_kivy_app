from base_kivy_app.utils import pretty_space


def test_pretty_space():
    assert pretty_space(10003045065) == '9.32 GB'
