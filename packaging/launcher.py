"""Einstiegspunkt fuer den gebauten Standalone-Build.

PyInstaller fuehrt das Startskript als eigenstaendiges Modul aus, deshalb
funktionieren relative Importe hier nicht - dieser Starter nutzt absolute.
"""

from pdfblack.app import main

raise SystemExit(main())
