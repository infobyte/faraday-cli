from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all(
    "faraday_plugins", include_py_files=True
)

hiddenimports += ["html2text", "bs4", "lxml.objectify"]
