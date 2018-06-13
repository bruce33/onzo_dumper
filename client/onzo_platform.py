# Embedded file name: client\onzo_platform.pyo
import os
import sys
WINDOWS = os.name == 'nt'
MAC = sys.platform == 'darwin'
LINUX = sys.platform.startswith('linux')