# SportOrg

### Build
`python setup.py build`

For build, you need `cx_Freeze`

### Packages

- PyQt5
- [sireader](https://pypi.python.org/pypi/sireader/1.0.1)
- [peewee](http://docs.peewee-orm.com/en/latest/peewee/quickstart.html)

Install packages
```
pip install package-name

pip install sireader
```

### Struct

```
<sportorg>/
    data/
    docs/
    img/
        icon/
    languages/
        <lang>/
            LC_MESSAGES/
                sportorg.mo
                sportorg.po
    sportorg/
        app/
            controller/
            models/
            view/
            plugin/
        lib/
```

