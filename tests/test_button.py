from digifiz.button import MfaButton


def test_missing_gpio_is_a_warning_not_a_crash():
    """Development machines have no GPIO. The dash must still start."""
    button = MfaButton(pin=17)
    button.start()  # gpiozero is absent or has no pins here
    assert button.available is False
    assert button.drain() == 0
    button.stop()


def test_presses_are_counted_and_drained():
    button = MfaButton(pin=17)
    button._on_press()
    button._on_press()
    assert button.drain() == 2
    assert button.drain() == 0
