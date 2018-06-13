# Embedded file name: client\internationalisation.pyo
import sys
import os
import gettext
gettext.install('onzo_uploader', 'locale', unicode=True, names=['ngettext'])
gettext.bind_textdomain_codeset('onzo_uploader', 'utf-8')