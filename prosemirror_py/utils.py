from icu import UnicodeString


def text_length(text):
    return UnicodeString(text).length()
